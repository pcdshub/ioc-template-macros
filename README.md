## ioc-template-macros
`ioc-template-macros` is a repo that provides the following tools for building templated IOCs:

- `expand`: a shell script that sets up a Python environment to run `expand.py`
- `expand.py`: a python script that reads from config files and uses the data within them to expand IOC templates.
- `RULES_EXPAND`: a file to include in a templated IOC `Makefile` such that when we `make` that IOC it uses this repo to expand the templates.

A typical templated IOC `Makefile` is something like:
```
# SLAC PCDS Makefile for building templated IOC instances
IOC_CFG  += $(wildcard *.cfg)
include /reg/g/pcds/controls/macro/RULES_EXPAND
```

## API

The `expand` script has two supported forms. There are others but they are not used in RULES_EXPAND.

The two forms look like:
```
expand -c CONFIG_FILE KEYWORD
expand -c CONFIG_FILE TEMPLATE_FILE OUTPUT_FILE
```

The first form finds the value of a keyword from the config file and sends it to stdout.

For example, if your config file is:

```
RELEASE = /some/path
ENGINEER = somebody
```

And you run:

```
expand -c path_to_that_file.cfg ENGINEER
```

Then "somebody" would be sent to stdout (with a trailing newline).
This is used in `RULES_EXPAND` to get the `RELEASE` path.

Note that you can use macros in your cfg file too, and they will be expanded here.
Some special environment variables such as `PATH` are also supported,
which during a standard `make` stores the directory containing the config file.

The second form uses the config file and the template file to create an output file.
Values from the config file will be referred to by the template
and will ultimately be used to create a fully-formed output.

Typically, templates come from common IOCs and
config files come from hutch-specific IOCs that reference the common IOC.


## Template Macro Language

All of the macro commands in the template files begin with "$$".

These can be:
- `$$VAR` or `$$(VAR)`
	- `VAR` is a variable name that is evaluated and inserted.
- `$$DIRNAME`
	- A special variable name that is the current directory name. (Not the
	  whole path!)
- `$$COUNT(INST)`
	- How many instantiations of `INST` are there.
- `$$LOOP(INST)`loop-body`$$ENDLOOP(INST)`
	- `INST` is the name of an instantiation from the config file.  The
	  macro processor loops over all of the named instantiation, and
	  inserts a copy of the loop-body with the variable replacements using
	  the parameters of the particular instance.
- `$$LOOP(N)`loop-body`$$ENDLOOP(N)`
	- `N` is an integer.  This will expand the loop-body `N` times, with `$$INDEX`
	  ranging from `0` to `N-1`.
- `$$TRANSLATE(VAR, "STR1", "STR2")`
	- `VAR` is a variable name that is evaluated and then has all of the
	  characters in `STR1` replaced by the corresponding characters in `STR2`.
	  The double-quotes are manditory!
- `$$IF(VAR)`if-body`$$ELSE(VAR)`else-body`$$ENDIF(VAR)`
	- A simple conditional.  The `$$ELSE` and else-body are optional.  If the
	  value of `VAR` is not "", expand the if-body, otherwise expand the else-body.
- `$$IF(VAR,if-body,else-body)`
	- An abbreviated form of the `$$IF`, useful for expressions and other cases
	  where neither body includes a comma.
- `$$IF(VAR,VAL)`if-body`$$ELSE(VAR)`else-body`$$ENDIF(VAR)`
	- Test if `VAR` is equal to the given value.
- `$$INCLUDE(FILENAME)`
	- Process the contents of the `FILENAME`.
- `$$CALC{EXPRESSION}` or `$$CALC{EXPRESSION,FORMAT}`
	- NOTE THE BRACKETS!!!  This allows arbitrary arithmetic.  The `EXPRESSION`
	  is expanded, and then evaluated as a mathematical expression.  Any
	  undefined atom is assumed to be zero.  Atoms within the expression do
	  not need to be prefixed by $$, but maybe.  (They should be if within a
	  $$LOOP inside the expression.)  The result is output as a decimal number,
	  or using the given format if one was given.

## Config Files

Configuration files are rather fussy, in that whitespace can only appear within
value strings and comments.  If a line starts with '#', it is a comment that runs
until the end of the line.

The configuration file has two types of statements.  Variable assignments have the
forms:
```
    VAR=VALUE
    VAR="VALUE"
    VAR='VALUE'
```
All of these define `$$VAR` to have the value `VALUE`.

Instantiations have the form:
```
    [ INAME: ] INST(PARAMLIST)
```
where `INAME` is the instance name, and the `PARAMLIST` is a comma-separated
list of entries of the forms:
```
    VAR=VALUE
    VAR="VALUE"
    VAR='VALUE'
    OTHERINSTn
    OTHERINAME
```
Instantiations are numbered, with the instantiation number assigned to a
special variable `$$INDEX`.  The first three types of parameters all create
global symbols of the form `$$INSTVARn` with value `VALUE`.  The last two forms
indicate that this instantiation uses a particular instantiation of
some other instantiation.

For example, if we have:
```
    E(X=Y)
    TEST:E(X=Z)
    A(B=C,D=F,E0)
    A(B=Q,D=R,TEST)
```
Then we have defined global symbols `$$EX0 = Y`, `$$EX1 = Z`, `$$AB0 = C`, `$$AD0 = F`,
`$$AB1 = Q` and `$$AD1 = R`.  If we `$$LOOP(A)`, then within the body of the loop,
we will have `$$B = C`, `$$D = F`, and `$$EX = Y` when `$$INDEX` is 0, and `$$B = Q`,
`$$D = R` and `$$EX = Z` when `$$INDEX` is 1.

Limited expansion is done while reading the config file as well.  The file is
expanded once with no variable definitions, and then processed to get a set
of variable definitions.  This is used to process the file again, and this
expansion is parsed to get the actual definions and instantiations used to
process the input file.  NOTE: THE DEFINITIONS USED ARE THE *FINAL* DEFINITIONS
IN THE CONFIG FILE!!!

## New Style Configs

New style: config files start with a set of definitions:
```
    VAR=VALUE
    VAR="VALUE"
    VAR='VALUE'
    VAR VALUE
    VAR "VALUE"
    VAR 'VALUE'
```
In the last three, any amount of whitespace can occur after `VAR` but before `VALUE`,
but whitespace in `VALUE` is preserved.

Then, we have instances: either as before or begun with
```
    INSTANCE xxx [ yyy ]
```
where `xxx` is the type of the instance and `yyy` is an optional name for this
instance.  In this case, the following lines consist of definitions as above,
with the exception that lines of the form:
```
    VAR VALUE
```
cannot have any whitespace in the `VALUE`.  Multiple assignments can be on a
single line.

The instance ends with either EOF or a new `INSTANCE`.

To clarify this, a config file such as:
```
    RELEASE=/reg/g/pcds/package/epics/3.14/ioc/common/ipimb/R2.0.17
    ARCH=linux-x86
    ENGINEER=Michael Browne (mcbrowne)
    LOCATION=MEC:R64A:24
    IOC_PV=IOC:MEC:IMB02

    EVR(NAME=MEC:XT2:EVR:01,TYPE=PMC)

    IPIMB(NAME=MEC:XT2:IPM:02,PORT=/dev/ttyPS3,BLDID=23,EVR0,TRIG=0)
    IPIMB(NAME=MEC:XT2:PIM:02,PORT=/dev/ttyPS2,BLDID=42,EVR0,TRIG=0)
    IPIMB(NAME=MEC:XT2:IPM:03,PORT=/dev/ttyPS1,BLDID=24,EVR0,TRIG=0)
    IPIMB(NAME=MEC:XT2:PIM:03,PORT=/dev/ttyPS0,BLDID=43,EVR0,TRIG=0)
```

could be written:
```
    RELEASE    /reg/g/pcds/package/epics/3.14/ioc/common/ipimb/R2.0.17
    ARCH       linux-x86
    ENGINEER   Michael Browne (mcbrowne)
    LOCATION   MEC:R64A:24
    IOC_PV     IOC:MEC:IMB02

    INSTANCE EVR
        NAME       MEC:XT2:EVR:01
        TYPE       PMC

    INSTANCE IPIMB
        NAME       MEC:XT2:IPM:02
        PORT       /dev/ttyPS3
        BLDID      23
        EVR0       TRIG=0

    INSTANCE IPIMB
        NAME       MEC:XT2:PIM:02
        PORT       /dev/ttyPS2
        BLDID      42
        EVR0       TRIG=0

    INSTANCE IPIMB
        NAME       MEC:XT2:IPM:03
        PORT       /dev/ttyPS1
        BLDID      24
        EVR0       TRIG=0

    INSTANCE IPIMB
        NAME       MEC:XT2:PIM:03
        PORT       /dev/ttyPS0
        BLDID      43
        EVR0       TRIG=0
```
