# Installation

This page describes how to install **toposkg-lib**.

## Requirements

ToposKG is intended to run in a Python environment. A typical setup requires:

- Python 3.10 or newer
- `pip`
- Java 8 (exclusively for the materialization functionality)

Depending on the enabled modules, additional geospatial or RDF libraries may be required.

### pip

We recommend using toposkg-lib through [pip](https://pypi.org/project/toposkg/).

```sh
pip install toposkg
```

If you want to include the translation functionality.

```sh
pip install toposkg[tl]
```

If you want to include the function calling functionality.

```sh
pip install toposkg[fc]
```

We recommend that you install this custom version of RDF-lib before using toposkg-lib.

```sh
pip install git+https://github.com/SKefalidis/rdflib-speed@main
```

Otherwise you can use the original rdflib.
