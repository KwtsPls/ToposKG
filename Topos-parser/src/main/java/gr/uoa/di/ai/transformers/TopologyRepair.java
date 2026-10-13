package gr.uoa.di.ai.transformers;

import org.locationtech.jts.geom.*;
import org.locationtech.jts.io.WKTReader;
import org.locationtech.jts.io.WKTWriter;
import org.locationtech.jts.operation.overlayng.OverlayNGRobust;
import org.locationtech.jts.operation.union.UnaryUnionOp;
import org.locationtech.jts.index.strtree.STRtree;
import org.locationtech.jts.operation.overlayng.OverlayNG;
import org.locationtech.jts.geom.util.GeometryFixer;
import org.semanticweb.yars.nx.Node;
import org.semanticweb.yars.nx.Literal;
import org.semanticweb.yars.nx.parser.NxParser;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.Collectors;

/**
 * Top-down correction of a target RDF administrative hierarchy.
 *
 * Each CSV-mapped entry entity gets its immutable ground-truth geometry.
 * Descendants are fitted into their corrected parent's geometry, with no
 * positive-area intersections or uncovered positive-area regions.
 *
 * LIMITATION: Ownership of ambiguous overlap/gap regions is heuristic,
 * and touching cannot be enforced for an externally specified adjacency graph
 * because none is supplied. Zero-area cracks are not tested independently.
 */
public final class TopologyRepair {
    static final String RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type";
    static final String HAS_GEOM = "http://www.opengis.net/ont/geosparql#hasGeometry";
    static final String AS_WKT = "http://www.opengis.net/ont/geosparql#asWKT";
    static final String WKT_TYPE = "http://www.opengis.net/ont/geosparql#wktLiteral";
    static final String DEFAULT_CRS = "http://www.opengis.net/def/crs/OGC/1.3/CRS84";
    static final GeometryFactory GF = new GeometryFactory();

    private final Path truthFile;
    private final Path targetFile;
    private final Path csvFile;
    private final Path outputFile;
    private final String truthClass;
    private final String targetClass;
    private final String parentPredicate;
    private final int threads;
    private final double epsilon;
    private final String targetWktPredicate; // null means standard GeoSPARQL
    private final String parentIdPredicate; // null means direct IRI relationships only

    /** Matches the project's transformer pattern: construct, then invoke repair(). */
    public TopologyRepair(String truthFile, String targetFile, String csvFile,
                          String outputFile, String truthClass, String targetClass,
                          String parentPredicate, int threads, double epsilon) {
        this(truthFile, targetFile, csvFile, outputFile, truthClass, targetClass,
                parentPredicate, threads, epsilon, null);
    }

    public TopologyRepair(String truthFile, String targetFile, String csvFile,
                          String outputFile, String truthClass, String targetClass,
                          String parentPredicate, int threads, double epsilon,
                          String targetWktPredicate) {
        this(truthFile, targetFile, csvFile, outputFile, truthClass, targetClass,
                parentPredicate, threads, epsilon, targetWktPredicate, null);
    }

    /** Optional ID predicate resolves literal parent identifiers (e.g. "IRL") to entity IRIs. */
    public TopologyRepair(String truthFile, String targetFile, String csvFile,
                          String outputFile, String truthClass, String targetClass,
                          String parentPredicate, int threads, double epsilon,
                          String targetWktPredicate, String parentIdPredicate) {
        this.parentIdPredicate = optionalPredicate(parentIdPredicate);
        this.targetWktPredicate = optionalPredicate(targetWktPredicate);
        this.truthFile = Path.of(truthFile);
        this.targetFile = Path.of(targetFile);
        this.csvFile = Path.of(csvFile);
        this.outputFile = Path.of(outputFile);
        this.truthClass = strip(truthClass);
        this.targetClass = strip(targetClass);
        this.parentPredicate = strip(parentPredicate);
        if (threads < 1) throw new IllegalArgumentException("threads must be >= 1");
        if (!Double.isFinite(epsilon) || epsilon < 0)
            throw new IllegalArgumentException("epsilon must be finite and >= 0");
        this.threads = threads;
        this.epsilon = epsilon;
    }

    public TopologyRepair(String truthFile, String targetFile, String csvFile,
                          String outputFile, String truthClass, String targetClass,
                          String parentPredicate) {
        this(truthFile, targetFile, csvFile, outputFile, truthClass, targetClass,
                parentPredicate, Runtime.getRuntime().availableProcessors(), 1e-9);
    }

    record WktData(Geometry geom, String crs) {}
    static final class Dataset {
        final Map<String,Set<String>> types = new HashMap<>();
        final Map<String,String> parent = new HashMap<>();
        final Map<String,List<String>> children = new HashMap<>();
        final Map<String,String> geomNodes = new HashMap<>();
        final Map<String,WktData> wkts = new HashMap<>();
        final Map<String,Geometry> entityGeoms = new HashMap<>();
        final Map<String,String> entityCrs = new HashMap<>();
    }
    static final class Result {
        final String id; final Geometry geom;
        Result(String id, Geometry geom){this.id=id;this.geom=geom;}
    }
    record GroupResult(String parent, List<Result> corrected, double uncoveredArea, double overlapArea, boolean skipped) {}

    // Instrumentation never alters operands or coordinates.
    private static final ConcurrentHashMap<Long, WorkStatus> ACTIVE = new ConcurrentHashMap<>();
    private static final AtomicLong OVERLAYS = new AtomicLong();
    private static final AtomicLong OVERLAY_NANOS = new AtomicLong();
    private static final long SLOW_NS = TimeUnit.SECONDS.toNanos(5);
    private static final long HEARTBEAT_NS = TimeUnit.SECONDS.toNanos(15);
    private static final class WorkStatus {
        final String parent;
        final int children;
        final long began = System.nanoTime();
        volatile String stage = "start";
        volatile long stageStarted = began;
        volatile String operation = "";
        volatile long operationStarted;
        volatile long overlayCount;
        WorkStatus(String p, int n) { parent = p; children = n; }
    }
    private static final ThreadLocal<WorkStatus> CURRENT = new ThreadLocal<>();
    private static void stage(String name) {
        WorkStatus st = CURRENT.get();
        if (st == null) return;
        long now = System.nanoTime();
        long duration = now - st.stageStarted;
        if (duration > SLOW_NS)
            log("SLOW stage parent=%s stage=%s duration=%.3fs", st.parent, st.stage, duration / 1e9);
        st.stage = name;
        st.stageStarted = now;
    }
    private static ScheduledExecutorService startMonitor() {
        ScheduledExecutorService monitor = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "topology-progress-monitor");
            t.setDaemon(true); return t;
        });
        monitor.scheduleAtFixedRate(() -> {
            long now = System.nanoTime();
            List<WorkStatus> pending = new ArrayList<>(ACTIVE.values());
            pending.sort(Comparator.comparingLong(v -> v.began));
            log("HEARTBEAT running=%d, total JTS overlays=%,d, JTS overlay seconds=%.2f",
                    pending.size(), OVERLAYS.get(), OVERLAY_NANOS.get() / 1e9);
            for (WorkStatus st : pending) {
                String operation = st.operation;
                double opTime = operation.isEmpty() ? 0.0 : (now - st.operationStarted) / 1e9;
                log("  parent=%s children=%d stage=%s elapsed=%.1fs overlays=%d activeJTS=%s activeJTSSeconds=%.1f",
                        st.parent, st.children, st.stage, (now-st.began)/1e9,
                        st.overlayCount, operation.isEmpty()?"none":operation, opTime);
            }
        }, 15, 15, TimeUnit.SECONDS);
        return monitor;
    }
    private static Geometry trackedOverlay(String label, Geometry a, Geometry b, int operation) {
        WorkStatus st = CURRENT.get();
        long start = System.nanoTime();
        if (st != null) { st.operation = label; st.operationStarted = start; }
        try { return OverlayNGRobust.overlay(a, b, operation); }
        finally {
            long elapsed = System.nanoTime() - start;
            OVERLAYS.incrementAndGet(); OVERLAY_NANOS.addAndGet(elapsed);
            if (st != null) {
                st.overlayCount++;
                if (elapsed > SLOW_NS)
                    log("SLOW JTS parent=%s op=%s duration=%.3fs pointsA=%d pointsB=%d",
                            st.parent, label, elapsed/1e9, a.getNumPoints(), b.getNumPoints());
                st.operation = "";
            }
        }
    }
    private static Geometry trackedUnion(Collection<Geometry> geometries) {
        WorkStatus st = CURRENT.get();
        long start = System.nanoTime();
        if (st != null) { st.operation="UnaryUnionOp"; st.operationStarted=start; }
        try { return UnaryUnionOp.union(geometries); }
        finally {
            long elapsed = System.nanoTime()-start;
            OVERLAYS.incrementAndGet(); OVERLAY_NANOS.addAndGet(elapsed);
            if (st != null) {
                st.overlayCount++;
                if (elapsed > SLOW_NS)
                    log("SLOW JTS parent=%s op=UnaryUnionOp duration=%.3fs polygons=%d",
                            st.parent, elapsed/1e9, geometries.size());
                st.operation="";
            }
        }
    }
    private static final long LOG_INTERVAL = 1_000_000L;
    private static void log(String format, Object... args) {
        System.out.printf(Locale.ROOT, "[TopologyRepair] " + format + "%n", args);
    }
    private static void progress(String phase, long triples) {
        if (triples % LOG_INTERVAL == 0) log("%s: %,d triples scanned", phase, triples);
    }

    /** Read only metadata and WKT needed by selected entities. For direct predicates
     * both are discovered in one pass; GeoSPARQL needs two passes because WKT
     * literals may precede hasGeometry statements in an arbitrary NT stream. */
    private static Dataset readRelevant(Path file, Set<String> entities,
                                        String directWktPredicate, String phase) throws Exception {
        Dataset ds = new Dataset();
        long phaseStart = System.nanoTime();
        log("%s: scanning RDF metadata for %,d requested entities", phase, entities.size());
        final boolean direct = directWktPredicate != null;
        final WKTReader reader = new WKTReader(GF);
        long count = 0, decoded = 0;
        try (InputStream in = new BufferedInputStream(Files.newInputStream(file), 1 << 20)) {
            NxParser parser = new NxParser(); parser.parse(in);
            while (parser.hasNext()) {
                Node[] t = parser.next(); progress(phase + " metadata", ++count);
                if (t.length != 3) continue;
                String p = iri(t[1]);
                if (!p.equals(RDF_TYPE) && !p.equals(HAS_GEOM)
                        && !(direct && p.equals(directWktPredicate))) continue;
                String subject = iri(t[0]);
                if (!entities.contains(subject)) continue;
                if (p.equals(RDF_TYPE)) {
                    ds.types.computeIfAbsent(subject, k -> new HashSet<>()).add(iri(t[2]));
                } else if (p.equals(HAS_GEOM) && !direct) {
                    ds.geomNodes.put(subject, iri(t[2]));
                } else if (direct && p.equals(directWktPredicate)) {
                    WktData wd = decodeWkt(t[2], null, reader, subject);
                    ds.entityGeoms.put(subject, wd.geom());
                    if (wd.crs() != null) ds.entityCrs.put(subject, wd.crs());
                    decoded++;
                }
            }
        }
        if (!direct) {
            Set<String> neededWktSubjects = new HashSet<>(ds.geomNodes.values());
            log("%s: metadata scan complete (%,d triples); %,d geometry subjects to load",
                    phase, count, neededWktSubjects.size());
            count = 0;
            try (InputStream in = new BufferedInputStream(Files.newInputStream(file), 1 << 20)) {
                NxParser parser = new NxParser(); parser.parse(in);
                while (parser.hasNext()) {
                    Node[] t = parser.next(); progress(phase + " WKT", ++count);
                    if (t.length != 3 || !iri(t[1]).equals(AS_WKT)) continue;
                    String subject = iri(t[0]);
                    if (!neededWktSubjects.contains(subject)) continue;
                    WktData wd = decodeWkt(t[2], DEFAULT_CRS, reader, subject);
                    ds.wkts.put(subject, wd);
                    decoded++;
                }
            }
            for (var e : ds.geomNodes.entrySet()) {
                WktData wd = ds.wkts.get(e.getValue());
                if (wd != null) {
                    ds.entityGeoms.put(e.getKey(), wd.geom());
                    if (wd.crs() != null) ds.entityCrs.put(e.getKey(), wd.crs());
                }
            }
            ds.wkts.clear();
        }
        log("%s: completed in %.2fs; %,d WKT literals parsed, %,d entity geometries",
                phase, (System.nanoTime() - phaseStart) / 1e9, decoded, ds.entityGeoms.size());
        return ds;
    }

    private static WktData decodeWkt(Node node, String defaultCrs,
                                     WKTReader reader, String subject) throws Exception {
        String lex = node instanceof Literal ? ((Literal)node).getLabel() : node.toString();
        String crs = defaultCrs;
        if (lex.startsWith("<")) {
            int end = lex.indexOf('>');
            if (end < 0) throw new IllegalArgumentException("Malformed CRS WKT literal: " + subject);
            crs = lex.substring(1, end);
            lex = lex.substring(end + 1).trim();
        }
        return new WktData(reader.read(lex), crs);
    }

    /** Build a compact reverse hierarchy once, traverse only the CSV root subtrees,
     * and retain only the reachable parent/child edges. */
    /** Cache key changes if the NT file, its modification time, or hierarchy predicates change. */
    private Path hierarchyCachePath() throws IOException {
        String fingerprint = targetFile.toAbsolutePath().normalize() + "|"
                + Files.size(targetFile) + "|" + Files.getLastModifiedTime(targetFile).toMillis()
                + "|" + parentPredicate + "|" + Objects.toString(parentIdPredicate, "");
        byte[] digest;
        try {
            digest = java.security.MessageDigest.getInstance("SHA-256")
                    .digest(fingerprint.getBytes(StandardCharsets.UTF_8));
        } catch (java.security.NoSuchAlgorithmException ex) {
            throw new IllegalStateException(ex);
        }
        String hex = java.util.HexFormat.of().formatHex(digest, 0, 12);
        Path folder = Path.of(System.getProperty("java.io.tmpdir"), "toposkg-topology-cache");
        return folder.resolve("hierarchy-" + hex + ".bin");
    }

    @SuppressWarnings("unchecked")
    private static Map<String, List<String>> loadHierarchyCache(Path cache) {
        if (!Files.isRegularFile(cache)) return null;
        try (ObjectInputStream in = new ObjectInputStream(
                new BufferedInputStream(Files.newInputStream(cache), 1 << 20))) {
            Object obj = in.readObject();
            if (obj instanceof HashMap<?, ?>) {
                return (Map<String, List<String>>) obj;
            }
        } catch (Exception e) {
            log("Hierarchy: cache unreadable (%s); rebuilding", e.getMessage());
        }
        return null;
    }

    private static void saveHierarchyCache(Path cache, Map<String, List<String>> reverse) {
        try {
            Files.createDirectories(cache.getParent());
            Path temp = Files.createTempFile(cache.getParent(), "building-", ".tmp");
            try {
                try (ObjectOutputStream out = new ObjectOutputStream(
                        new BufferedOutputStream(Files.newOutputStream(temp), 1 << 20))) {
                    out.writeObject(reverse);
                }
                try {
                    Files.move(temp, cache, StandardCopyOption.REPLACE_EXISTING,
                            StandardCopyOption.ATOMIC_MOVE);
                } catch (java.nio.file.AtomicMoveNotSupportedException ex) {
                    Files.move(temp, cache, StandardCopyOption.REPLACE_EXISTING);
                }
                log("Hierarchy: cache saved: %s", cache);
            } finally {
                Files.deleteIfExists(temp);
            }
        } catch (IOException ex) {
            log("Hierarchy: unable to save cache: %s", ex.getMessage());
        }
    }

    private Dataset readReachableHierarchy(Set<String> roots) throws Exception {
        log("Hierarchy: starting discovery from %,d CSV target roots", roots.size());
        Path cache = hierarchyCachePath();
        Map<String, List<String>> reverse = loadHierarchyCache(cache);
        if (reverse == null) {
            log("Hierarchy: cache miss; building indexes from source RDF");
            reverse = new HashMap<>();
            Map<String, String> entityById = new HashMap<>();
            long count = 0, ids = 0;
            if (parentIdPredicate != null) {
                try (InputStream in = new BufferedInputStream(Files.newInputStream(targetFile))) {
                    NxParser parser = new NxParser(); parser.parse(in);
                    while (parser.hasNext()) {
                        Node[] t = parser.next(); progress("Hierarchy ID index", ++count);
                        if (t.length == 3 && iri(t[1]).equals(parentIdPredicate) && t[2] instanceof Literal) {
                            if (entityById.putIfAbsent(((Literal)t[2]).getLabel(), iri(t[0])) == null) ids++;
                        }
                    }
                }
                log("Hierarchy: ID index complete (%,d triples scanned, %,d distinct IDs)", count, ids);
            }
            // First resolved parent wins, in input file order. Do not emit warnings
            // about unrelated countries; only reachable duplicates will be reported.
            Map<String, String> firstParent = new HashMap<>();

            long relations = 0, unresolved = 0, duplicateParents = 0;
            count = 0;
            try (InputStream in = new BufferedInputStream(Files.newInputStream(targetFile))) {
                NxParser parser = new NxParser(); parser.parse(in);
                while (parser.hasNext()) {
                    Node[] t = parser.next(); progress("Hierarchy relationships", ++count);
                    if (t.length != 3 || !iri(t[1]).equals(parentPredicate)) continue;
                    relations++;
                    String child = iri(t[0]);
                    boolean literal = t[2] instanceof Literal;
                    if (literal && parentIdPredicate == null) { unresolved++; continue; }
                    String parent = literal ? entityById.get(((Literal)t[2]).getLabel()) : iri(t[2]);
                    if (parent == null) { unresolved++; continue; }
                    String previous = firstParent.putIfAbsent(child, parent);
                    if (previous == null) reverse.computeIfAbsent(parent, k -> new ArrayList<>()).add(child);
                    else if (!previous.equals(parent)) duplicateParents++;
                }
            }
            log("Hierarchy: relationship index complete (%,d triples, %,d relationships, %,d unresolved, %,d conflicting extra parents)",
                    count, relations, unresolved, duplicateParents);
            // Release ID dictionary as soon as relationships have been resolved.
            entityById.clear();
            saveHierarchyCache(cache, reverse);
        } else {
            log("Hierarchy: reused cached index (%,d parents)", reverse.size());
        }
        Dataset reachable = new Dataset();
        Set<String> visited = new LinkedHashSet<>(roots);
        ArrayDeque<String> queue = new ArrayDeque<>(roots);
        long edges = 0, skippedCycles = 0;
        while (!queue.isEmpty()) {
            String parent = queue.removeFirst();
            for (String child : reverse.getOrDefault(parent, List.of())) {
                if (!visited.add(child)) { skippedCycles++; continue; }
                reachable.parent.put(child, parent);
                reachable.children.computeIfAbsent(parent, k -> new ArrayList<>()).add(child);
                queue.addLast(child);
                edges++;
            }
        }
        log("Hierarchy: reachable entities %,d (roots %,d, descendants %,d); retained edges %,d; repeated/cyclic links %,d",
                visited.size(), roots.size(), visited.size() - roots.size(), edges, skippedCycles);
        return reachable;
    }

    public void repair() throws Exception {
        long started = System.nanoTime();
        log("Reading root correspondences: %s", csvFile);
        Map<String,String> correspondence = readCsv(csvFile);
        if (correspondence.isEmpty()) throw new IllegalArgumentException("Empty mappings CSV");
        Set<String> sourceRoots = new LinkedHashSet<>(correspondence.keySet());
        Set<String> targetRoots = new LinkedHashSet<>(correspondence.values());
        // readCsv() already resolves conflicting target mappings (first occurrence wins).
        log("Loaded %,d mappings (%,d distinct target roots)", correspondence.size(), targetRoots.size());

        long phaseStarted = System.nanoTime();
        Dataset hierarchy = readReachableHierarchy(targetRoots);
        log("Timing: hierarchy discovery %.2fs", (System.nanoTime() - phaseStarted) / 1e9);
        Set<String> reachableIds = new HashSet<>(targetRoots);
        reachableIds.addAll(hierarchy.parent.keySet());
        // Avoid parsing geometries and types for unrelated countries.
        phaseStarted = System.nanoTime();
        Dataset truth = readRelevant(truthFile, sourceRoots, null, "Ground truth");
        log("Timing: ground-truth extraction %.2fs", (System.nanoTime() - phaseStarted) / 1e9);
        phaseStarted = System.nanoTime();
        Dataset target = readRelevant(targetFile, reachableIds, targetWktPredicate, "Target");
        log("Timing: target extraction %.2fs", (System.nanoTime() - phaseStarted) / 1e9);
        target.children.putAll(hierarchy.children);
        target.parent.putAll(hierarchy.parent);
        hierarchy.children.clear(); hierarchy.parent.clear();
        log("RDF loading complete; starting top-down repair with %d threads, epsilon=%.9g", threads, epsilon);

        Map<String,Geometry> corrected = new HashMap<>();
        Map<String,String> correctedCrs = new HashMap<>();
        List<String> roots = new ArrayList<>();
        for (var e : correspondence.entrySet()) {
            String source=e.getKey(), dest=e.getValue();
            if (!truth.types.getOrDefault(source, Set.of()).contains(truthClass))
                throw new IllegalArgumentException("Ground truth root has wrong class: " + source);
            if (!target.types.getOrDefault(dest, Set.of()).contains(targetClass))
                throw new IllegalArgumentException("Target root has wrong class: " + dest);
            Geometry g=truth.entityGeoms.get(source);
            String sourceCrs = truth.entityCrs.getOrDefault(source, DEFAULT_CRS);
            String targetCrs = target.entityCrs.get(dest);
            if (targetCrs != null && !targetCrs.equals(sourceCrs))
                throw new IllegalArgumentException("Different CRS for target entry " + dest
                        + ": ground truth=" + sourceCrs + ", target=" + targetCrs
                        + ". Reproject before repairing.");
            if (g==null) throw new IllegalArgumentException("Missing ground truth geometry: " + source);
            if (!g.isValid() || !isPolygonal(g)) throw new IllegalArgumentException("Invalid ground truth geometry: " + source);
            if (!roots.contains(dest)) roots.add(dest);
            if (corrected.putIfAbsent(dest,g.copy()) != null)
                throw new IllegalArgumentException("Duplicate target entry mapping: " + dest);
            correctedCrs.put(dest,truth.entityCrs.getOrDefault(source, DEFAULT_CRS));
        }
        // All roots need to share the same CRS with their descendants.
        int workerCount = Math.max(1, Math.min(threads, Math.max(1, reachableIds.size() / 40)));
        log("Adaptive parallelism: requested %d, using %d worker(s)", threads, workerCount);
        ExecutorService pool=Executors.newFixedThreadPool(workerCount);
        ScheduledExecutorService monitor = startMonitor();
        Set<String> visited=new HashSet<>(roots);
        List<String> frontier=new ArrayList<>(roots);
        int level=0, modified=0;
        phaseStarted = System.nanoTime();
        try {
            while(!frontier.isEmpty()) {
                log("Level %d: %,d parent candidates, %,d corrected descendants so far", level, frontier.size(), modified);
                List<Future<GroupResult>> tasks=new ArrayList<>();
                final int levelForLog = level;
                for (String p : frontier) {
                    List<String> raw = target.children.getOrDefault(p,List.of());
                    if (raw.isEmpty()) continue;
                    List<String> children = new ArrayList<>(raw);
                    Geometry parentGeom=corrected.get(p);
                    if(parentGeom==null) throw new IllegalStateException("Uncorrected parent: "+p);
                    tasks.add(pool.submit(() -> {
                        WorkStatus status = new WorkStatus(p, children.size());
                        long threadId = Thread.currentThread().getId();
                        ACTIVE.put(threadId, status);
                        CURRENT.set(status);
                        log("START parent=%s level=%d children=%d parentPoints=%d parentArea=%.9g",
                                p, levelForLog, children.size(), parentGeom.getNumPoints(), parentGeom.getArea());
                        try {
                            GroupResult result = repairGroup(p, parentGeom, children, target.entityGeoms, epsilon);
                            log("DONE parent=%s duration=%.3fs overlays=%d skipped=%s",
                                    p, (System.nanoTime()-status.began)/1e9, status.overlayCount, result.skipped);
                            return result;
                        } catch (RuntimeException ex) {
                            log("FAILED parent=%s stage=%s operation=%s duration=%.3fs: %s",
                                    p, status.stage, status.operation, (System.nanoTime()-status.began)/1e9, ex);
                            throw ex;
                        } finally { CURRENT.remove(); ACTIVE.remove(threadId); }
                    }));
                }
                log("Level %d: submitted %,d parent groups", level, tasks.size());
                List<String> next=new ArrayList<>();
                int finishedGroups = 0;
                for(Future<GroupResult> future:tasks) {
                    GroupResult r=future.get();
                    finishedGroups++;
                    if (finishedGroups % 100 == 0 || finishedGroups == tasks.size())
                        log("Level %d: completed %,d / %,d parent groups", level, finishedGroups, tasks.size());
                    if (r.skipped) {
                        System.err.printf("[WARN] Skipping subtree under %s: all immediate child geometries lie outside "
                                + "the corrected parent or are empty. Check CRS, hierarchy, and entry mappings.%n", r.parent);
                        continue;
                    }
                    for(Result child:r.corrected) {
                        if(!visited.add(child.id))
                            throw new IllegalStateException("Cycle or multi-parent hierarchy at: "+child.id);
                        corrected.put(child.id, child.geom);
                        correctedCrs.put(child.id,correctedCrs.get(r.parent));
                        next.add(child.id);modified++;
                    }
                    System.out.printf(Locale.ROOT,"[level %d] %s: %d children, input overlap area %.9g, input missing area %.9g%n",
                            level,r.parent,r.corrected.size(),r.overlapArea,r.uncoveredArea);
                }
                frontier=next;
                level++;
            }
        } finally { pool.shutdownNow(); monitor.shutdownNow(); }
        log("Timing: geometry correction %.2fs", (System.nanoTime() - phaseStarted) / 1e9);
        log("Writing repaired RDF: %,d corrected geometries -> %s", corrected.size(), outputFile);
        phaseStarted = System.nanoTime();
        write(target,targetFile,outputFile,corrected,correctedCrs,targetWktPredicate);
        log("Timing: RDF output writing %.2fs", (System.nanoTime() - phaseStarted) / 1e9);
        log("Elapsed %.1f seconds", (System.nanoTime() - started) / 1e9);
        System.out.printf("Completed: %d matched roots, %d descendants processed, %d levels; output: %s%n",
                roots.size(),modified,level,outputFile);
    }

    private static GroupResult repairGroup(String pid, Geometry parent, List<String> ids,
                                           Map<String,Geometry> original, double eps) {
        stage("clipping children");
        // A singleton forms an exact parent partition: the only possible child
        // geometry satisfying coverage (and no overlaps) IS the parent.
        // Keep previous skip behavior if an existing child has zero overlap.
        if (ids.size() == 1) {
            String childId = ids.get(0);
            Geometry input = original.get(childId);
            if (input == null || input.isEmpty() || !isPolygonal(input)) {
                log("INFER singleton parent=%s child=%s: missing geometry; assigning exact parent polygon", pid, childId);
                return new GroupResult(pid, List.of(new Result(childId, parent.copy())), parent.getArea(), 0, false);
            }
            Geometry valid = fix(input);
            if (!parent.getEnvelopeInternal().intersects(valid.getEnvelopeInternal())
                    || !parent.intersects(valid)
                    || !parent.relate(valid, "T********")) {
                log("SKIP singleton parent=%s child=%s: no positive-area intersection", pid, childId);
                return new GroupResult(pid, List.of(), parent.getArea(), 0, true);
            }
            // Exact topology: same parent polygon, no JTS union/difference needed.
            // The parent-minus-clipped-child input gap is reported by area subtraction.
            double insideArea = parent.covers(valid) ? valid.getArea() :
                    polygonal(intersection(parent, valid)).getArea();
            double missingArea = Math.max(0, parent.getArea() - insideArea);
            log("FAST singleton parent=%s child=%s inputMissingArea=%.9g", pid, childId, missingArea);
            return new GroupResult(pid, List.of(new Result(childId, parent.copy())), missingArea, 0, false);
        }
        // Deterministic order; larger pre-existing intersections with parent win contested areas.
        List<Result> clipped=new ArrayList<>();
        List<String> missingIds=new ArrayList<>();
        for(String id: ids) {
            Geometry g=original.get(id);
            if(g==null || g.isEmpty() || !isPolygonal(g)) {
                // A missing (or non-polygonal) geometry is represented by an
                // empty polygon until the known children have been allocated.
                // Its territory is inferred from the residual parent area.
                missingIds.add(id);
                clipped.add(new Result(id, GF.createPolygon()));
                continue;
            }
            g=fix(g);
            Geometry clippedGeom;
            if (!parent.getEnvelopeInternal().intersects(g.getEnvelopeInternal())) {
                clippedGeom = GF.createPolygon();
            } else if (parent.covers(g)) {
                clippedGeom = g; // No overlay needed when the parent fully contains the child.
            } else {
                clippedGeom = polygonal(intersection(parent,g));
            }
            clipped.add(new Result(id,clippedGeom));
        }
        stage("sort and fast-path validation");
        clipped.sort(Comparator.<Result>comparingDouble(r->-r.geom.getArea()).thenComparing(r->r.id));

        // Fast path: correctly partitioned children need no overlap/gap processing.
        // Use a union and topological equality (area alone cannot detect an
        // overlap balanced by an equal-sized gap).
        if (missingIds.isEmpty() && !clipped.isEmpty()) {
            double childAreaSum = 0;
            boolean allValid = true;
            for (Result child : clipped) {
                childAreaSum += child.geom.getArea();
                allValid &= child.geom.isValid();
            }
            if (allValid && Math.abs(childAreaSum - parent.getArea()) <= eps) {
                Geometry candidateUnion = unionAll(clipped.stream()
                        .map(r -> r.geom).collect(Collectors.toList()));
                if (Math.abs(candidateUnion.getArea() - childAreaSum) <= eps
                        && candidateUnion.equalsTopo(parent)) {
                    return new GroupResult(pid, clipped, 0.0, 0.0, false);
                }
            }
        }

        // All children may have valid polygon geometries but zero intersection
        // with their corrected parent (e.g., incorrect mapping or mismatched CRS).
        // There is no spatial evidence with which to assign the parent's area.
        // Do not invent a polygon or crash: keep these descendants unchanged
        // in the RDF output and do not recurse into this branch.
        if (missingIds.isEmpty() && clipped.stream().noneMatch(r -> !r.geom.isEmpty())) {
            System.err.printf(Locale.ROOT,
                    "[WARN] Parent %s: %d children, none intersects parent (parent area %.9g).%n",
                    pid, ids.size(), parent.getArea());
            return new GroupResult(pid, List.of(), parent.getArea(), 0.0, true);
        }

        // Index input envelopes. For a child, only higher-priority children
        // whose envelopes intersect can contest any of its area.
        stage("allocate overlapping regions");
        STRtree candidateIndex = new STRtree();
        for (int i=0;i<clipped.size();i++)
            if (!clipped.get(i).geom.isEmpty())
                candidateIndex.insert(clipped.get(i).geom.getEnvelopeInternal(),i);
        candidateIndex.build();
        List<Result> allocated=new ArrayList<>();
        double inputSum=0;
        int clippedOverlaps = 0;
        for(int i=0;i<clipped.size();i++) {
            Result r=clipped.get(i);
            inputSum+=r.geom.getArea();
            List<Geometry> earlier=new ArrayList<>();
            for(Object obj:candidateIndex.query(r.geom.getEnvelopeInternal())) {
                int j=(Integer)obj;
                if(j<i)earlier.add(clipped.get(j).geom);
            }
            Geometry remaining=r.geom;
            if(!earlier.isEmpty() && !r.geom.isEmpty()) {
                // Envelope collisions can be boundary-only; avoid union when there is no area overlap.
                List<Geometry> actual = new ArrayList<>();
                for (Geometry blocker : earlier) {
                    if (r.geom.relate(blocker, "T********")) actual.add(blocker);
                }
                if (!actual.isEmpty()) {
                    clippedOverlaps++;
                    Geometry blockers = actual.size() == 1 ? actual.get(0) : unionAll(actual);
                    remaining = polygonal(difference(r.geom, blockers));
                }
            }
            allocated.add(new Result(r.id,remaining));
        }
        List<Geometry> occupiedParts=allocated.stream().map(r->r.geom).collect(Collectors.toList());
        stage("calculate occupied union and gaps");
        Geometry occupied = unionAll(occupiedParts);
        double overlap=Math.max(0,inputSum-occupied.getArea());
        Geometry gaps=polygonal(difference(parent,occupied));
        double missing=gaps.getArea();
        List<Geometry> pieces=new ArrayList<>();
        if (!missingIds.isEmpty()) {
            stage("infer missing child territories");
            // All unclaimed territory is reserved for children without geometry.
            // Do NOT let known siblings absorb territory belonging to them.
            List<Geometry> inferred = inferMissingTerritories(gaps, missingIds.size(), eps);
            Map<String,Geometry> inferredById = new HashMap<>();
            for (int i=0; i<missingIds.size(); i++)
                inferredById.put(missingIds.get(i), inferred.get(i));
            for (int i=0; i<allocated.size(); i++) {
                Result child = allocated.get(i);
                Geometry inferredChild = inferredById.get(child.id);
                if (inferredChild != null) allocated.set(i, new Result(child.id, inferredChild));
            }
            System.err.printf(Locale.ROOT,
                    "[INFERRED] Parent %s: generated %d child geometries from residual area %.9g; %s%n",
                    pid, missingIds.size(), missing,
                    missingIds.size() == 1 ? "unique residual allocation" :
                            "equal-area provisional partition; boundaries NOT authoritative");
        } else {
            pieces.addAll(polygonParts(gaps));
        }
        // Iteratively assign remaining positive-area gaps. Give preference to a
        // neighbor with the longest already-shared boundary; fallback to proximity.
        stage("allocate gap pieces");
        while(!pieces.isEmpty()) {
            int bestGap=-1,bestOwner=-1;
            double bestShared=-1;
            for(int gi=0;gi<pieces.size();gi++) {
                Geometry gap=pieces.get(gi);
                for(int ci=0;ci<allocated.size();ci++) {
                    Geometry child=allocated.get(ci).geom;
                    if(child.isEmpty()) continue;
                    if(!gap.getEnvelopeInternal().intersects(child.getEnvelopeInternal())) continue;
                    double shared=sharedBoundaryLength(gap,child);
                    if(shared>bestShared) {bestShared=shared;bestGap=gi;bestOwner=ci;}
                }
            }
            // A gap may be completely disconnected from every current child.
            // In that case no bounding boxes intersect, so pick an uncovered
            // piece and let the nearest-child fallback below determine its owner.
            if (bestGap < 0) {
                bestGap = 0;
                bestShared = 0;
            }
            Geometry gap=pieces.remove(bestGap);
            if(bestShared<=eps) {
                double distance=Double.POSITIVE_INFINITY;
                for(int ci=0;ci<allocated.size();ci++) {
                    Geometry candidate=allocated.get(ci).geom;
                    Geometry fallback=candidate.isEmpty()?clipped.get(ci).geom:candidate;
                    if(fallback.isEmpty()) continue;
                    double d=gap.distance(fallback);
                    if(d<distance){distance=d;bestOwner=ci;}
                }
            }
            if(bestOwner<0) {
                // Defensive diagnostic: this should be unreachable because
                // at least one clipped child is nonempty (checked above).
                throw new IllegalStateException("No usable child despite nonempty clipped children for " + pid);
            }
            Result owner=allocated.get(bestOwner);
            allocated.set(bestOwner,new Result(owner.id,polygonal(union(owner.geom,gap))));
        }
        // Robust second pass: recompute the actual residual instead of assuming
        // that the first assignment exhausted every uncovered polygon.
        // This also catches additional pieces exposed by overlay roundoff.
        stage("validate and repair residual coverage");
        Geometry finalUnion = unionAll(allocated.stream().map(r -> r.geom).collect(Collectors.toList()));
        for (int retry = 0; retry < 4; retry++) {
            Geometry residual = polygonal(difference(parent, finalUnion));
            if (residual.isEmpty() || residual.getArea() <= eps) break;

            boolean changed = false;
            for (Geometry piece : polygonParts(residual)) {
                if (piece.isEmpty() || piece.getArea() <= eps) continue;
                int best = -1;
                double longest = -1;
                double nearest = Double.POSITIVE_INFINITY;
                for (int ci = 0; ci < allocated.size(); ci++) {
                    Geometry candidate = allocated.get(ci).geom;
                    if (candidate.isEmpty()) continue;
                    double shared = 0;
                    if (piece.getEnvelopeInternal().intersects(candidate.getEnvelopeInternal())) {
                        shared = sharedBoundaryLength(piece,candidate);
                    }
                    double distance = piece.distance(candidate);
                    if (shared > longest || (shared == longest && distance < nearest)) {
                        best = ci;
                        longest = shared;
                        nearest = distance;
                    }
                }
                if (best < 0) {
                    throw new IllegalStateException("No usable child for residual gap in " + pid);
                }
                Result owner = allocated.get(best);
                allocated.set(best, new Result(owner.id,
                        polygonal(union(owner.geom, piece))));
                changed = true;
            }
            if (!changed) break;
            finalUnion = unionAll(allocated.stream().map(r -> r.geom).collect(Collectors.toList()));
        }
        stage("final topology validation");
        double remainingGap=polygonal(difference(parent,finalUnion)).getArea();
        // Every allocated child is clipped to parent; union cannot overflow except overlay roundoff.
        double overflow = parent.covers(finalUnion) ? 0.0 : polygonal(difference(finalUnion,parent)).getArea();
        if(remainingGap>eps || overflow>eps)
            throw new IllegalStateException("Coverage validation failed for " + pid + ": gap="+remainingGap+", overflow="+overflow);
        double sum=0;
        for(Result r:allocated) {
            if(!r.geom.isValid()) throw new IllegalStateException("Invalid result: "+r.id);
            sum+=r.geom.getArea();
        }
        if(sum-finalUnion.getArea()>eps)
            throw new IllegalStateException("Children overlap by area in " + pid);
        return new GroupResult(pid,allocated,missing,overlap,false);
    }

    /**
     * Infer missing child territories from parent area not claimed by known children.
     * With one missing child the residual is uniquely determined. With multiple
     * missing children, the individual boundaries are unknowable from parentage
     * alone. As an explicit, deterministic *provisional* fallback, divide the
     * residual into approximately equal-area longitude/X bands.
     *
     * This mode prioritizes coverage consistency, NOT geographic truth.
     * For authoritative boundaries, supply location anchors or child polygons.
     */
    private static List<Geometry> inferMissingTerritories(Geometry residual, int count, double epsilon) {
        if (count < 1) throw new IllegalArgumentException("count must be positive");
        List<Geometry> inferred = new ArrayList<>(count);
        if (count == 1) {
            inferred.add(residual);
            return inferred;
        }
        if (residual.isEmpty() || residual.getArea() == 0) {
            for (int i=0; i<count; i++) inferred.add(GF.createPolygon());
            return inferred;
        }
        Envelope env = residual.getEnvelopeInternal();
        double pad = Math.max(1.0, Math.max(env.getWidth(), env.getHeight()));
        Geometry remaining = residual;
        for (int i=0; i<count-1; i++) {
            double targetArea = remaining.getArea() / (count-i);
            double low = env.getMinX();
            double high = env.getMaxX();
            // Find X where the intersection of the remaining geometry with
            // the half-plane left of X covers the requested area.
            // Area-aware termination avoids 55 expensive polygon overlays per split.
            double allowableAreaError = Math.max(Math.max(epsilon * 0.05, targetArea * 1e-8), 1e-14);
            for (int iter=0; iter<36; iter++) {
                double mid = low+(high-low)*0.5;
                Geometry left = GF.toGeometry(new Envelope(
                        env.getMinX()-pad, mid, env.getMinY()-pad, env.getMaxY()+pad));
                double a = polygonal(intersection(remaining,left)).getArea();
                if (Math.abs(a - targetArea) <= allowableAreaError) {
                    low = high = mid;
                    break;
                }
                if (a < targetArea) low=mid; else high=mid;
            }
            Geometry left = GF.toGeometry(new Envelope(
                    env.getMinX()-pad, high, env.getMinY()-pad, env.getMaxY()+pad));
            Geometry piece = polygonal(intersection(remaining,left));
            inferred.add(piece);
            remaining = polygonal(difference(remaining,piece));
        }
        inferred.add(remaining);
        return inferred;
    }

    /** Geometry overlay shortcuts reduce expensive OverlayNG invocations. */
    static Geometry unionAll(Collection<Geometry> geometries) {
        List<Geometry> nonempty = new ArrayList<>();
        for (Geometry g : geometries) if (g != null && !g.isEmpty()) nonempty.add(g);
        if (nonempty.isEmpty()) return GF.createPolygon();
        if (nonempty.size() == 1) return nonempty.get(0);
        return polygonal(trackedUnion(nonempty));
    }

    private static double sharedBoundaryLength(Geometry a, Geometry b) {
        if (a.isEmpty() || b.isEmpty() ||
                !a.getEnvelopeInternal().intersects(b.getEnvelopeInternal())) return 0;
        Geometry ba = a.getBoundary(), bb = b.getBoundary();
        if (!ba.getEnvelopeInternal().intersects(bb.getEnvelopeInternal())) return 0;
        return intersection(ba, bb).getLength();
    }

    static Geometry intersection(Geometry a,Geometry b){
        if (a.isEmpty() || b.isEmpty() || !a.getEnvelopeInternal().intersects(b.getEnvelopeInternal()))
            return GF.createPolygon();
        return trackedOverlay("intersection", a,b,OverlayNG.INTERSECTION);
    }
    static Geometry difference(Geometry a,Geometry b){
        if (a.isEmpty() || b.isEmpty()) return a;
        if (!a.getEnvelopeInternal().intersects(b.getEnvelopeInternal())) return a;
        return trackedOverlay("difference", a,b,OverlayNG.DIFFERENCE);
    }
    static Geometry union(Geometry a,Geometry b){
        if (a.isEmpty()) return b;
        if (b.isEmpty()) return a;
        if (!a.getEnvelopeInternal().intersects(b.getEnvelopeInternal())) return unionAll(List.of(a,b));
        return trackedOverlay("union", a,b,OverlayNG.UNION);
    }
    static boolean isPolygonal(Geometry g){return g instanceof Polygon || g instanceof MultiPolygon;}
    static Geometry fix(Geometry g){return g.isValid()?g:GeometryFixer.fix(g);}
    static List<Polygon> polygonParts(Geometry g) {
        List<Polygon> polys = new ArrayList<>();
        collectPolygons(g, polys);
        return polys;
    }

    private static void collectPolygons(Geometry g, List<Polygon> polys) {
        if (g == null || g.isEmpty()) return;
        if (g instanceof Polygon p) {
            polys.add(p);
        } else if (g instanceof GeometryCollection) {
            for (int i = 0; i < g.getNumGeometries(); i++) {
                collectPolygons(g.getGeometryN(i), polys);
            }
        }
    }

    static Geometry polygonal(Geometry g) {
        List<Polygon> polys = polygonParts(g);
        if (polys.isEmpty()) return GF.createPolygon();
        if (polys.size() == 1) return polys.get(0);
        return GF.createMultiPolygon(polys.toArray(new Polygon[0]));
    }
    record ParentReference(String child, String value, boolean literal) {}

    static Dataset read(Path file,String parentPredicate,String directWktPredicate) throws Exception {
        return read(file, parentPredicate, directWktPredicate, null);
    }

    static Dataset read(Path file,String parentPredicate,String directWktPredicate,
                        String parentIdPredicate) throws Exception {
        Dataset ds=new Dataset();
        // Resolve IDs after the full file has been scanned: ID triples may follow relationship triples.
        Map<String,String> entityById = new HashMap<>();
        List<ParentReference> references = new ArrayList<>();
        try(InputStream in=new BufferedInputStream(Files.newInputStream(file))) {
            NxParser parser=new NxParser();parser.parse(in);
            while(parser.hasNext()) {
                Node[] t=parser.next(); if(t.length!=3)continue;
                String s=iri(t[0]),p=iri(t[1]);
                if(p.equals(RDF_TYPE))ds.types.computeIfAbsent(s,k->new HashSet<>()).add(iri(t[2]));
                else if(directWktPredicate == null && p.equals(HAS_GEOM))ds.geomNodes.put(s,iri(t[2]));
                else if(p.equals(directWktPredicate == null ? AS_WKT : directWktPredicate)){
                    String lex=t[2] instanceof Literal ? ((Literal)t[2]).getLabel():t[2].toString();
                    // Plain direct WKT has no declared CRS; do not silently label it CRS84.
                    String crs=directWktPredicate == null ? DEFAULT_CRS : null;
                    if(lex.startsWith("<")) {
                        int end=lex.indexOf('>');if(end<0)throw new IllegalArgumentException("Malformed CRS literal: "+s);
                        crs=lex.substring(1,end); lex=lex.substring(end+1).trim();
                    }
                    Geometry geom=new WKTReader(GF).read(lex);
                    ds.wkts.put(s,new WktData(geom,crs));
                } else if(parentIdPredicate != null && p.equals(parentIdPredicate)
                        && t[2] instanceof Literal) {
                    String id = ((Literal)t[2]).getLabel();
                    String firstEntity = entityById.putIfAbsent(id, s);
                    if (firstEntity != null && !firstEntity.equals(s)) {
                        System.err.printf("[WARN] Duplicate entity ID %s: keeping %s, ignoring %s%n",
                                id, firstEntity, s);
                    }
                } else if(parentPredicate!=null && p.equals(parentPredicate)) {
                    // Direct IRI objects work in either mode. Literal IDs are only resolved
                    // when an ID predicate has been supplied.
                    boolean literal = t[2] instanceof Literal;
                    if (literal && parentIdPredicate == null) {
                        System.err.printf("[WARN] Literal parent ID for %s ignored; "
                                + "supply parentIdPredicate to resolve it%n", s);
                    } else {
                        String value = literal ? ((Literal)t[2]).getLabel() : iri(t[2]);
                        references.add(new ParentReference(s, value, literal));
                    }
                }
            }
        }
        for (ParentReference ref : references) {
            String par = ref.literal ? entityById.get(ref.value) : ref.value;
            if (par == null) {
                System.err.printf("[WARN] No entity with ID %s for child %s; skipping relationship%n",
                        ref.value, ref.child);
                continue;
            }
            String firstParent = ds.parent.putIfAbsent(ref.child, par);
            if (firstParent == null) {
                ds.children.computeIfAbsent(par, k -> new ArrayList<>()).add(ref.child);
            } else if (!firstParent.equals(par)) {
                System.err.printf("[WARN] Multiple parents for %s: keeping %s, ignoring %s%n",
                        ref.child, firstParent, par);
            }
        }
        if (directWktPredicate != null) {
            for (var e : ds.wkts.entrySet()) {
                ds.entityGeoms.put(e.getKey(), e.getValue().geom);
                if (e.getValue().crs != null) ds.entityCrs.put(e.getKey(), e.getValue().crs);
            }
        } else {
            for(var e:ds.geomNodes.entrySet()) {
                WktData wd=ds.wkts.get(e.getValue());
                if(wd!=null) {ds.entityGeoms.put(e.getKey(),wd.geom);ds.entityCrs.put(e.getKey(),wd.crs);}
            }
        }
        return ds;
    }
    static String iri(Node n) {
        String t=n.toString();
        return t.startsWith("<")&&t.endsWith(">")?t.substring(1,t.length()-1):t;
    }
    static Map<String,String> readCsv(Path csv) throws IOException {
        Map<String,String> result = new LinkedHashMap<>();
        try (BufferedReader r = Files.newBufferedReader(csv, StandardCharsets.UTF_8)) {
            String header = r.readLine();
            if (header == null) throw new IllegalArgumentException("Empty mapping CSV: " + csv);
            List<String> columns = parseCsvRow(header.replace("\uFEFF", ""));
            if (columns.size() != 2 || !(columns.get(0).trim().equalsIgnoreCase("source")
                    || columns.get(0).trim().equalsIgnoreCase("source_entity"))
                    || !(columns.get(1).trim().equalsIgnoreCase("target")
                    || columns.get(1).trim().equalsIgnoreCase("target_entity"))) {
                throw new IllegalArgumentException(
                        "CSV must have header source,target or source_entity,target_entity");
            }
            Map<String, String> firstSourceByTarget = new HashMap<>();
            int skippedConflictingTargets = 0;
            String line;
            long rowNumber = 1;
            while ((line = r.readLine()) != null) {
                rowNumber++;
                if (line.isBlank()) continue;
                List<String> fields;
                try {
                    fields = parseCsvRow(line);
                } catch (IllegalArgumentException ex) {
                    throw new IllegalArgumentException("Invalid CSV at line " + rowNumber + ": " + ex.getMessage(), ex);
                }
                if (fields.size() != 2) {
                    throw new IllegalArgumentException("Expected 2 CSV fields at line " + rowNumber + ": " + line);
                }
                String src = strip(fields.get(0));
                String dst = strip(fields.get(1));
                if (src.isEmpty() || dst.isEmpty()) {
                    throw new IllegalArgumentException("Empty source or target at CSV line " + rowNumber);
                }
                String oldTarget = result.get(src);
                if (oldTarget != null) {
                    if (!oldTarget.equals(dst)) {
                        System.err.printf("[WARN] CSV line %d: source %s already maps to %s; ignoring %s%n",
                                rowNumber, src, oldTarget, dst);
                    }
                    continue;
                }
                String firstSource = firstSourceByTarget.putIfAbsent(dst, src);
                if (firstSource != null) {
                    skippedConflictingTargets++;
                    System.err.printf("[WARN] CSV line %d: target %s already mapped from %s; ignoring source %s%n",
                            rowNumber, dst, firstSource, src);
                    continue;
                }
                result.put(src, dst);
            }
            if (skippedConflictingTargets > 0) {
                System.out.printf("[TopologyRepair] Ignored %,d conflicting target-root mappings (first wins)%n",
                        skippedConflictingTargets);
            }
        }
        return result;
    }

    /** Parse one CSV record, respecting quoted fields, commas and doubled quotes. */
    static List<String> parseCsvRow(String row) {
        List<String> fields = new ArrayList<>();
        StringBuilder field = new StringBuilder();
        boolean inQuotes = false;
        boolean afterQuote = false;
        boolean fieldStarted = false;
        for (int i = 0; i < row.length(); i++) {
            char ch = row.charAt(i);
            if (inQuotes) {
                if (ch == '"') {
                    if (i + 1 < row.length() && row.charAt(i + 1) == '"') {
                        field.append('"');
                        i++;
                    } else {
                        inQuotes = false;
                        afterQuote = true;
                    }
                } else {
                    field.append(ch);
                }
            } else if (ch == ',') {
                fields.add(field.toString().trim());
                field.setLength(0);
                afterQuote = false;
                fieldStarted = false;
            } else if (ch == '"') {
                if (!fieldStarted && field.toString().isBlank() && !afterQuote) {
                    field.setLength(0);
                    inQuotes = true;
                    fieldStarted = true;
                } else {
                    throw new IllegalArgumentException("Unexpected quote in CSV field");
                }
            } else if (afterQuote) {
                if (!Character.isWhitespace(ch)) {
                    throw new IllegalArgumentException("Unexpected text after closing quote");
                }
            } else {
                field.append(ch);
                if (!Character.isWhitespace(ch)) fieldStarted = true;
            }
        }
        if (inQuotes) throw new IllegalArgumentException("Unclosed quoted CSV field");
        fields.add(field.toString().trim());
        return fields;
    }
    static String optionalPredicate(String uri) {
        if (uri == null || uri.isBlank() || uri.equals("-") || uri.equalsIgnoreCase("null"))
            return null;
        return strip(uri);
    }
    static String strip(String s) {
        s=s.trim();if(s.startsWith("<")&&s.endsWith(">"))return s.substring(1,s.length()-1);
        return s;
    }
    static void write(Dataset target,Path inFile,Path outFile,Map<String,Geometry> fixed,
                      Map<String,String> crs, String directWktPredicate) throws Exception {
        // Rewrite geometry literals belonging to fixed entities; untouched triples preserved.
        // Assumes that each corrected entity has its own geometry node (not shared by others).
        Map<String,String> replacements=new HashMap<>();
        Map<String,String> extra=new LinkedHashMap<>();
        for(var e:fixed.entrySet()) {
            String node;
            if (directWktPredicate != null) {
                node = e.getKey(); // subject directly contains the WKT literal
            } else {
                node=target.geomNodes.get(e.getKey());
                if(node==null) {
                    node=e.getKey()+"/correctedGeometry";
                    extra.put(e.getKey(),node);
                }
            }
            if (replacements.containsKey(node)) {
                throw new IllegalStateException("Shared geometry node: "+node);
            }
            String wkt = new WKTWriter().write(e.getValue());
            if (directWktPredicate == null) {
                String c=crs.getOrDefault(e.getKey(),DEFAULT_CRS);
                wkt="<"+c+"> "+wkt;
            }
            replacements.put(node,wkt);
        }
        Path dest=outFile.toAbsolutePath();
        if(dest.getParent()!=null)Files.createDirectories(dest.getParent());
        if(inFile.toAbsolutePath().equals(dest))throw new IllegalArgumentException("Output must differ from input");
        Set<String> seen=new HashSet<>();
        long writtenTriples = 0;
        String literalPredicate = directWktPredicate == null ? AS_WKT : directWktPredicate;
        // NT guarantees one statement per line. Copy almost every line verbatim,
        // avoiding NxParser's Node allocation and WKT literal parsing during output.
        // Only inspect subject/predicate tokens; preserve all unrelated RDF syntax.
        try (BufferedWriter out=new BufferedWriter(Files.newBufferedWriter(dest, StandardCharsets.UTF_8), 1 << 20);
             BufferedReader in=new BufferedReader(Files.newBufferedReader(inFile, StandardCharsets.UTF_8), 1 << 20)) {
            String line;
            while ((line = in.readLine()) != null) {
                progress("Output rewrite", ++writtenTriples);
                String subj = replacementSubject(line, literalPredicate, replacements);
                if (subj != null) {
                    if (!seen.add(subj)) throw new IllegalStateException("Duplicate WKT predicate for " + subj);
                    writeLiteralTriple(out,subj,literalPredicate,replacements.get(subj),directWktPredicate == null);
                } else {
                    out.write(line); out.newLine();
                }
            }
            for (var e:extra.entrySet()) {
                out.write('<'+e.getKey()+"> <"+HAS_GEOM+"> <"+e.getValue()+"> .\n");
            }
            for (var e:replacements.entrySet()) {
                if(!seen.contains(e.getKey())) {
                    writeLiteralTriple(out,e.getKey(),literalPredicate,e.getValue(),directWktPredicate == null);
                }
            }
        }
        log("Output rewrite complete: %,d input triples copied/replaced; %,d WKT replacements generated", writtenTriples, replacements.size());
    }
    /** Return a subject only for a WKT triple that needs replacement. */
    private static String replacementSubject(String line, String predicate, Map<String,String> replacements) {
        int len = line.length();
        int i = 0;
        while (i < len && Character.isWhitespace(line.charAt(i))) i++;
        if (i == len || line.charAt(i) != '<') return null;
        int end = line.indexOf('>', i + 1);
        if (end < 0) return null;
        String subject = line.substring(i + 1, end);
        if (!replacements.containsKey(subject)) return null;
        i = end + 1;
        if (i == len || !Character.isWhitespace(line.charAt(i))) return null;
        while (i < len && Character.isWhitespace(line.charAt(i))) i++;
        if (i == len || line.charAt(i) != '<') return null;
        end = line.indexOf('>', i + 1);
        if (end < 0 || !line.regionMatches(i + 1, predicate, 0, predicate.length())
                || end - i - 1 != predicate.length()) return null;
        return subject;
    }

    static void writeLiteralTriple(BufferedWriter out,String subject,String predicate,
                                   String lexical, boolean geoSparqlLiteral) throws IOException {
        String escaped=lexical.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r");
        out.write('<'+subject+"> <"+predicate+"> \""+escaped+"\"" +
                (geoSparqlLiteral ? "^^<"+WKT_TYPE+">" : "") + " .\n");
    }
}
