# cf2 (configurator 2)
`cf2` is a tool for configuring a Linux system from human-readable configuration files.
Its intended purpose is to provide a reproducible platform to run system level
experiments.

# Setup
First `cd` into the project root directory.
Then run `setup.sh` in the project root directory to set up the project's Python virtual environment.

> **Important:** You **MUST** run `setup.sh` **WHILST** the project directory is the current working directory in order for the scripts in `bin` to work.

A convenience script `cf2` to run the tool is provided in the `bin` directory.
The purpose of this script is to let you use `cf2` from the command line without having to worry about virtual environments etc.
Under the hood, `bin/cf2` switches to the virtual environment and runs the actual cf2 Python script.
Make `bin/cf2` available on `$PATH` and it will be usable from anywhere.

# Requirements
`cf2` has been tested with Python 3.11.4.

`cf2` uses _PyYAML_ to read/write YAML files.
If running `cf2` outside of the provided virtual environment setup (creating by running `setup.sh`), you need to install _PyYAML_.
Install PyYAML (preferably within a virtual environment) with `python3 -m pip install pyyaml`.

# Documentation
## Usage
Run `./cf2.py --help` for usage.

## Software Architecture
This section is intended for those who wish to modify and enchance `cf2.py`.
If you only wish to you use the tool as-is you may skip this section.

The key data structure is `TypecheckedModel`.
This data structure has two components: `__rawdata` - which contains the data,
and `__metamodel` which contains the metamodel that the data has been
type-checked against.
An instance of `TypecheckedModel` can be thought of as the raw data
with the additional invariant that it is correctly typechecked to the
corresponidng metamodel.

The raw data is represented by a tree.
Python dictionaries are used for internal nodes and scalar data types are used
for leaf nodes.
This is the form that `yaml.safe_load()` produces.
The structure of the tree is as described by the Metamodel.

Raw data must _never_ be modified in place.
Once raw data is loaded, it should be considered constant.
If you truly need to modify any element, create a new raw data tree from the 
old tree, performing the modifications in the process.
Then typecheck the new raw data tree to produce a new `TypecheckedModel`.
The method `CreateTypecheckedModel()` (in `MetaModel`) does this for you.

The philosophy for reading data is the same irregardless of whether that data
be from a configuration file or from the system itself:
first read the raw data, then typecheck it.
Performing these typechecks reduces the likelihood of bugs.

### Metamodel
The metamodel (`MetaModel`) describes the abstract structure of the configuration space.
The configuration space is a tree of nested configuration options.
The metamodel __never__ contains configuration data; it only describes it's
structure.
It is also a conveniant place to store information associated with certain 
parts of the abstract configuration tree (such as whether a particular field 
can actually be set in the system or is read only).

Since the metamodel is intended only to represent the structure, it doesn't
define any methods that do actual data processing or system manipulation.
Instead, it enables the "visitor" pattern by providing an `AcceptVisitor` 
method that accepts a `MetaTreeVisitor`.
For an example of using this interface, see the `MetaTreePrinter` class.


