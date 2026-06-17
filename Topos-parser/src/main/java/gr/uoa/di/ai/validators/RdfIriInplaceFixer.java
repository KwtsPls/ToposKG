package gr.uoa.di.ai.validators;

import org.eclipse.rdf4j.model.Statement;
import org.eclipse.rdf4j.rio.RDFFormat;
import org.eclipse.rdf4j.rio.RDFHandler;
import org.eclipse.rdf4j.rio.RDFHandlerException;
import org.eclipse.rdf4j.rio.RDFParser;
import org.eclipse.rdf4j.rio.Rio;
import org.eclipse.rdf4j.rio.helpers.BasicParserSettings;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

public final class RdfIriInplaceFixer {

    private static final Charset UTF8 = StandardCharsets.UTF_8;
    private static final char[] HEX = "0123456789ABCDEF".toCharArray();

    private RdfIriInplaceFixer() {
    }

    public static Stats fixInPlace(
            Path input,
            boolean createBackup,
            boolean validateWithRio,
            boolean fixPrefixedNames
    ) throws Exception {

        if (!Files.isRegularFile(input)) {
            throw new IOException("Not a regular file: " + input);
        }

        Path absoluteInput = input.toAbsolutePath();
        Path parent = absoluteInput.getParent() == null ? Path.of(".") : absoluteInput.getParent();
        Path temp = Files.createTempFile(parent, absoluteInput.getFileName().toString(), ".fixed.tmp");

        Stats stats = new Stats();
        LexerState lexerState = new LexerState();

        boolean writeSucceeded = false;

        try (BufferedReader reader = Files.newBufferedReader(absoluteInput, UTF8);
             BufferedWriter writer = Files.newBufferedWriter(temp, UTF8)) {

            String line;
            while ((line = reader.readLine()) != null) {
                stats.linesRead++;

                String fixed = fixLine(line, lexerState, stats, fixPrefixedNames);

                if (!fixed.equals(line)) {
                    stats.linesChanged++;
                }

                writer.write(fixed);
                writer.write('\n');
            }

            writeSucceeded = true;
        } finally {
            if (!writeSucceeded) {
                Files.deleteIfExists(temp);
            }
        }

        if (validateWithRio) {
            try {
                validateWithRio(temp);
            } catch (Exception e) {
                System.err.println("The repaired temporary file did not pass RDF4J/Rio validation.");
                System.err.println("Original file was left untouched.");
                System.err.println("Temporary repaired file kept here: " + temp);
                throw e;
            }
        }

        if (createBackup) {
            Path backup = uniqueBackupPath(absoluteInput);
            Files.copy(absoluteInput, backup);
            System.out.println("Backup created: " + backup);
        }

        try {
            Files.move(temp, absoluteInput, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (AtomicMoveNotSupportedException e) {
            Files.move(temp, absoluteInput, StandardCopyOption.REPLACE_EXISTING);
        }

        return stats;
    }

    private static String fixLine(
            String line,
            LexerState state,
            Stats stats,
            boolean fixPrefixedNames
    ) {
        StringBuilder out = new StringBuilder(line.length());
        int i = 0;

        while (i < line.length()) {
            char c = line.charAt(i);

            if (state.inLiteral) {
                out.append(c);

                if (c == '\\') {
                    if (i + 1 < line.length()) {
                        out.append(line.charAt(i + 1));
                        i += 2;
                    } else {
                        i++;
                    }
                    continue;
                }

                if (state.tripleQuoted) {
                    if (c == state.quoteChar && startsTripleQuote(line, i, state.quoteChar)) {
                        out.append(line.charAt(i + 1));
                        out.append(line.charAt(i + 2));
                        i += 3;
                        state.leaveLiteral();
                    } else {
                        i++;
                    }
                } else {
                    if (c == state.quoteChar) {
                        state.leaveLiteral();
                    }
                    i++;
                }

                continue;
            }

            if (c == '#') {
                out.append(line.substring(i));
                break;
            }

            if (c == '<') {
                int end = line.indexOf('>', i + 1);

                if (end < 0) {
                    out.append(c);
                    i++;
                    continue;
                }

                String iri = line.substring(i + 1, end);
                String fixedIri = fixIriContent(iri, stats);

                if (!fixedIri.equals(iri)) {
                    stats.angleBracketIrisChanged++;
                }

                out.append('<').append(fixedIri).append('>');
                i = end + 1;
                continue;
            }

            if (fixPrefixedNames && isPossiblePrefixedNameStart(line, i)) {
                Token token = tryReadPrefixedName(line, i);

                if (token != null) {
                    String fixedLocal = fixIriContent(token.localPart, stats);

                    if (!fixedLocal.equals(token.localPart)) {
                        stats.prefixedNamesChanged++;
                        out.append(token.prefix).append(':').append(fixedLocal);
                    } else {
                        out.append(token.raw);
                    }

                    i = token.endExclusive;
                    continue;
                }
            }

            if (c == '"' || c == '\'') {
                if (startsTripleQuote(line, i, c)) {
                    out.append(c).append(c).append(c);
                    state.enterLiteral(c, true);
                    i += 3;
                } else {
                    out.append(c);
                    state.enterLiteral(c, false);
                    i++;
                }
                continue;
            }

            out.append(c);
            i++;
        }

        return out.toString();
    }

    private static String fixIriContent(String iri, Stats stats) {
        StringBuilder out = null;

        for (int i = 0; i < iri.length(); ) {
            int cp = iri.codePointAt(i);
            int charLen = Character.charCount(cp);

            boolean mustEncode;

            if (cp == '%') {
                mustEncode = !hasValidPercentEncodingAt(iri, i);
                if (mustEncode) {
                    stats.illegalPercentSignsEncoded++;
                }
            } else {
                mustEncode = isIllegalIriRefChar(cp);
            }

            if (mustEncode) {
                if (out == null) {
                    out = new StringBuilder(iri.length() + 16);
                    out.append(iri, 0, i);
                }

                appendPercentEncodedUtf8(out, cp);
                stats.charactersEncoded++;
                stats.recordEncodedCharacter(cp);
            } else if (out != null) {
                out.appendCodePoint(cp);
            }

            i += charLen;
        }

        return out == null ? iri : out.toString();
    }

    private static boolean isIllegalIriRefChar(int cp) {
        if (cp <= 0x20 || Character.isISOControl(cp)) {
            return true;
        }

        return switch (cp) {
            case '<', '>', '"', '{', '}', '|', '^', '`', '\\', '[', ']' -> true;
            default -> false;
        };
    }

    private static boolean hasValidPercentEncodingAt(String s, int percentIndex) {
        return percentIndex + 2 < s.length()
                && isHexDigit(s.charAt(percentIndex + 1))
                && isHexDigit(s.charAt(percentIndex + 2));
    }

    private static boolean isHexDigit(char c) {
        return (c >= '0' && c <= '9')
                || (c >= 'A' && c <= 'F')
                || (c >= 'a' && c <= 'f');
    }

    private static void appendPercentEncodedUtf8(StringBuilder out, int codePoint) {
        String s = new String(Character.toChars(codePoint));
        byte[] bytes = s.getBytes(UTF8);

        for (byte b : bytes) {
            int unsigned = b & 0xFF;
            out.append('%');
            out.append(HEX[(unsigned >>> 4) & 0x0F]);
            out.append(HEX[unsigned & 0x0F]);
        }
    }

    private static boolean startsTripleQuote(String line, int index, char quote) {
        return index + 2 < line.length()
                && line.charAt(index) == quote
                && line.charAt(index + 1) == quote
                && line.charAt(index + 2) == quote;
    }

    private static boolean isPossiblePrefixedNameStart(String line, int index) {
        char c = line.charAt(index);

        if (!(Character.isLetter(c) || c == '_' || c == ':')) {
            return false;
        }

        if (index == 0) {
            return true;
        }

        char prev = line.charAt(index - 1);

        return Character.isWhitespace(prev)
                || prev == '^'
                || prev == '['
                || prev == '('
                || prev == ';'
                || prev == ',';
    }

    private static Token tryReadPrefixedName(String line, int start) {
        int i = start;

        while (i < line.length() && isPrefixedTokenChar(line.charAt(i))) {
            i++;
        }

        if (i == start) {
            return null;
        }

        String raw = line.substring(start, i);
        int colon = raw.indexOf(':');

        if (colon < 0) {
            return null;
        }

        String prefix = raw.substring(0, colon);
        String local = raw.substring(colon + 1);

        if ("_".equals(prefix)) {
            return null;
        }

        if (!prefix.isEmpty() && !isSimplePrefix(prefix)) {
            return null;
        }

        if (local.isEmpty()) {
            return null;
        }

        return new Token(raw, prefix, local, i);
    }

    private static boolean isPrefixedTokenChar(char c) {
        return !Character.isWhitespace(c)
                && c != '<'
                && c != '>'
                && c != ';'
                && c != ','
                && c != '.'
                && c != '('
                && c != ')'
                && c != '#';
    }

    private static boolean isSimplePrefix(String prefix) {
        if (prefix.isEmpty()) {
            return true;
        }

        char first = prefix.charAt(0);

        if (!(Character.isLetter(first) || first == '_')) {
            return false;
        }

        for (int i = 1; i < prefix.length(); i++) {
            char c = prefix.charAt(i);

            if (!(Character.isLetterOrDigit(c) || c == '_' || c == '-')) {
                return false;
            }
        }

        return true;
    }

    private static void validateWithRio(Path file) throws Exception {
        Optional<RDFFormat> detected = Rio.getParserFormatForFileName(file.getFileName().toString());
        RDFFormat format = detected.orElse(RDFFormat.NTRIPLES);

        RDFParser parser = Rio.createParser(format);
        parser.getParserConfig().set(BasicParserSettings.VERIFY_URI_SYNTAX, true);
        parser.setRDFHandler(NO_OP_HANDLER);

        try (InputStream in = Files.newInputStream(file)) {
            parser.parse(in, file.toUri().toString());
        }
    }

    private static final RDFHandler NO_OP_HANDLER = new RDFHandler() {
        @Override
        public void startRDF() throws RDFHandlerException {
        }

        @Override
        public void endRDF() throws RDFHandlerException {
        }

        @Override
        public void handleNamespace(String prefix, String uri) throws RDFHandlerException {
        }

        @Override
        public void handleStatement(Statement st) throws RDFHandlerException {
        }

        @Override
        public void handleComment(String comment) throws RDFHandlerException {
        }
    };

    private static Path uniqueBackupPath(Path input) {
        String timestamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss"));
        Path backup = input.resolveSibling(input.getFileName() + "." + timestamp + ".bak");

        int counter = 1;
        while (Files.exists(backup)) {
            backup = input.resolveSibling(input.getFileName() + "." + timestamp + "." + counter + ".bak");
            counter++;
        }

        return backup;
    }

    private static final class LexerState {
        private boolean inLiteral;
        private boolean tripleQuoted;
        private char quoteChar;

        private void enterLiteral(char quoteChar, boolean tripleQuoted) {
            this.inLiteral = true;
            this.quoteChar = quoteChar;
            this.tripleQuoted = tripleQuoted;
        }

        private void leaveLiteral() {
            this.inLiteral = false;
            this.tripleQuoted = false;
            this.quoteChar = 0;
        }
    }

    private static final class Token {
        private final String raw;
        private final String prefix;
        private final String localPart;
        private final int endExclusive;

        private Token(String raw, String prefix, String localPart, int endExclusive) {
            this.raw = raw;
            this.prefix = prefix;
            this.localPart = localPart;
            this.endExclusive = endExclusive;
        }
    }

    public static final class Stats {
        private long linesRead;
        private long linesChanged;
        private long angleBracketIrisChanged;
        private long prefixedNamesChanged;
        private long charactersEncoded;
        private long illegalPercentSignsEncoded;
        private final Map<String, Long> encodedCharacterCounts = new LinkedHashMap<>();

        private void recordEncodedCharacter(int codePoint) {
            String key = "U+" + String.format("%04X", codePoint) + " " + printable(codePoint);
            encodedCharacterCounts.merge(key, 1L, Long::sum);
        }

        private static String printable(int codePoint) {
            return switch (codePoint) {
                case ' ' -> "SPACE";
                case '\t' -> "TAB";
                case '\n' -> "LF";
                case '\r' -> "CR";
                default -> "'" + new String(Character.toChars(codePoint)) + "'";
            };
        }

        @Override
        public String toString() {
            StringBuilder sb = new StringBuilder();

            sb.append("Repair finished.\n");
            sb.append("Lines read: ").append(linesRead).append('\n');
            sb.append("Lines changed: ").append(linesChanged).append('\n');
            sb.append("<...> IRIs changed: ").append(angleBracketIrisChanged).append('\n');
            sb.append("Prefixed names changed: ").append(prefixedNamesChanged).append('\n');
            sb.append("Characters encoded: ").append(charactersEncoded).append('\n');
            sb.append("Illegal percent signs encoded: ").append(illegalPercentSignsEncoded).append('\n');

            if (!encodedCharacterCounts.isEmpty()) {
                sb.append("Encoded character counts:\n");
                for (Map.Entry<String, Long> e : encodedCharacterCounts.entrySet()) {
                    sb.append("  ").append(e.getKey()).append(" -> ").append(e.getValue()).append('\n');
                }
            }

            return sb.toString();
        }
    }
}