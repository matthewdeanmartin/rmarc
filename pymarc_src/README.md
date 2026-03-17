```
_|_|_|    _|    _|  _|_|_|  _|_|      _|_|_|  _|  _|_|    _|_|_|
_|    _|  _|    _|  _|    _|    _|  _|    _|  _|_|      _|
_|    _|  _|    _|  _|    _|    _|  _|    _|  _|        _|
_|_|_|      _|_|_|  _|    _|    _|    _|_|_|  _|          _|_|_|
_|              _|
_|          _|_|
```

[![Build status](https://gitlab.com/pymarc/pymarc/badges/main/pipeline.svg)](https://gitlab.com/pymarc/pymarc/-/commits/main)

pymarc is a python library for working with bibliographic data encoded in
[MARC21](https://en.wikipedia.org/wiki/MARC_standards). It provides an API for
reading, writing and modifying MARC records. It was mostly designed to be an
emergency eject seat, for getting your data assets out of MARC and into some
kind of saner representation. However over the years it has been used to create
and modify MARC records, since despite [repeated
calls](https://web.archive.org/web/20170731163019/http://www.marc-must-die.info/index.php/Main_Page)
for it to die as a format, MARC seems to be living quite happily as a zombie.

Below are some common examples of how you might want to use pymarc. If
you run across an example that you think should be here please send a
pull request.

You can read pymarc documentation [here](https://pymarc.readthedocs.io/en/latest/).

## Installation

You'll probably just want to use pip to install pymarc:

    pip install pymarc
    
## Reading

Most often you will have some MARC data and will want to extract data
from it. Here's an example of reading a batch of records and printing out
the title. If you are curious this example uses the batch file
available here in pymarc repository:

```python
from pymarc import MARCReader
with open('test/marc.dat', 'rb') as fh:
    reader = MARCReader(fh)
    for record in reader:
        print(record.title)
```
```
The pragmatic programmer : from journeyman to master /
Programming Python /
Learning Python /
Python cookbook /
Python programming for the absolute beginner /
Web programming : techniques for integrating Python, Linux, Apache, and MySQL /
Python programming on Win32 /
Python programming : an introduction to computer science /
Python Web programming /
Core python programming /
Python and Tkinter programming /
Game programming with Python, Lua, and Ruby /
Python programming patterns /
Python programming with the Java class libraries : a tutorial for building Web
and Enterprise applications /
Learn to program using Python : a tutorial for hobbyists, self-starters, and all
who want to learn the art of computer programming /
Programming with Python /
BSD Sockets programming from a multi-language perspective /
Design patterns : elements of reusable object-oriented software /
Introduction to algorithms /
ANSI Common Lisp /
```

A `pymarc.Record` object has a few handy properties like `title` for getting at
bits of a bibliographic record, others include: `author`, `isbn`, `subjects`,
`location`, `notes`, `physicaldescription`, `publisher`, `pubyear`, `issn`,
`issn_title`. But really, to work with MARC data you need to understand the
numeric field tags and subfield codes that are used to designate various bits
of information. There is a lot more data hidden in a MARC record than these
helper properties provide access to. For example the `title` property works by
extracting the information from the `245` field, subfields `a` and `b` behind
the scenes. You can access `245a` like so:

```python
print(record['245']['a'])
```

Some fields like subjects can repeat. In cases like that you will want to use
`get_fields` to get all of them as `pymarc.Field` objects, which you can then
interact with further:

```python
for f in record.get_fields('650'):
    print(f)
```

If you are new to MARC fields [Understanding
MARC](http://www.loc.gov/marc/umb/) is a pretty good primer, and the [MARC 21
Formats](http://www.loc.gov/marc/marcdocz.html) page at the Library of Congress 
is a good reference once you understand the basics.

## Writing

*Note: As of v5.0.0 `Subfield` is used to create subfields. Prior to v5,
subfields were constructed and accessed as a list of strings, e.g., `[code,
value, code, value]`. In v5.0.0 this has been changed to organize the subfields
into a list of tuples, e.g., `[(code, value), (code, value)]`. The `Subfield`
is implemented as a `NamedTuple` so that the tuples can be constructed as
`Subfield(code=code, value=value)`. The old style of creating subfields is no
longer supported. Attempting to pass a list of strings to the `subfields`
parameter for the `Field` constructor will raise a `ValueError`. For
convenience the `Field.convert_legacy_subfields` class method can be used to 
convert a legacy list of strings into a list of `Subfield`s.*

Here's an example of creating a record and writing it out to a file.

```python
from pymarc import Record, Field, Subfield, Indicators

record = Record()
record.add_field(
    Field(
        tag='245',
        indicators=Indicators('0', '1'),
        subfields=[
            Subfield(code='a', value='The pragmatic programmer : '),
            Subfield(code='b', value='from journeyman to master /'),
            Subfield(code='c', value='Andrew Hunt, David Thomas.')
        ]))
with open('file.dat', 'wb') as out:
    out.write(record.as_marc())
```

To convert from the old string list to a list of `Subfield`s, the `.convert_legacy_subfields` class method
is provided on the `Field` class.

```python
from pymarc import Field, Subfield

legacy_fields: list[str] = ['a', 'The pragmatic programmer : ',
                            'b', 'from journeyman to master /',
                            'c', 'Andrew Hunt, David Thomas']

coded_fields: list[Subfield] = Field.convert_legacy_subfields(legacy_fields)
```

## Updating

Updating works the same way, you read it in, modify it, and then write it out
again:

```python
from pymarc import MARCReader
with open('test/marc.dat', 'rb') as fh:
    reader = MARCReader(fh)
    record = next(reader)
    record['245']['a'] = 'The Zombie Programmer : '
with open('file.dat', 'wb') as out:
    out.write(record.as_marc())
```


## JSON and XML

If you find yourself using MARC data a fair bit, and distributing it, you may
make other developers a bit happier by using the JSON or XML serializations. The
main benefit to using XML or JSON is that the UTF8 character encoding is used,
rather than the frustratingly archaic MARC8 encoding. Also they will be able to
use standard JSON and XML reading/writing tools to get at the data they want
instead of some crazy MARC processing library like, ahem, pymarc.

**XML**

To parse a file of MARCXML records you can:

```python

from pymarc import parse_xml_to_array

records = parse_xml_to_array('test/batch.xml')
```

If you have a large XML file and would rather not read them all into memory you
can:

```python

from pymarc import map_xml

def print_title(r):
    print(r.title)

map_xml(print_title, 'test/batch.xml')
```

Also, if you prefer you can pass in a file like object in addition to the path
to both *map_xml* and *parse_xml_to_array*:

```python
from pymarc import parse_xml_to_array

records = parse_xml_to_array(open('test/batch.xml'))
```

**JSON**

JSON support is fairly minimal in that you can call a `pymarc.Record`'s
`as_json()` method to return JSON for a given MARC Record:

```python
from pymarc import MARCReader

with open('test/one.dat','rb') as fh:
    reader = MARCReader(fh)
    for record in reader:
        print(record.as_json(indent=2))
```

```json
{
  "leader": "01060cam  22002894a 4500",
  "fields": [
    {
      "001": "11778504"
    },
    {
      "010": {
        "ind1": " ",
        "subfields": [
          {
            "a": "   99043581 "
          }
        ],
        "ind2": " "
      }
    },
    {
      "100": {
        "ind1": "1",
        "subfields": [
          {
            "a": "Hunt, Andrew,"
          },
          {
            "d": "1964-"
          }
        ],
        "ind2": " "
      }
    },
    {
      "245": {
        "ind1": "1",
        "subfields": [
          {
            "a": "The pragmatic programmer :"
          },
          {
            "b": "from journeyman to master /"
          },
          {
            "c": "Andrew Hunt, David Thomas."
          }
        ],
        "ind2": "4"
      }
    },
    {
      "260": {
        "ind1": " ",
        "subfields": [
          {
            "a": "Reading, Mass :"
          },
          {
            "b": "Addison-Wesley,"
          },
          {
            "c": "2000."
          }
        ],
        "ind2": " "
      }
    },
    {
      "300": {
        "ind1": " ",
        "subfields": [
          {
            "a": "xxiv, 321 p. ;"
          },
          {
            "c": "24 cm."
          }
        ],
        "ind2": " "
      }
    },
    {
      "504": {
        "ind1": " ",
        "subfields": [
          {
            "a": "Includes bibliographical references."
          }
        ],
        "ind2": " "
      }
    },
    {
      "650": {
        "ind1": " ",
        "subfields": [
          {
            "a": "Computer programming."
          }
        ],
        "ind2": "0"
      }
    },
    {
      "700": {
        "ind1": "1",
        "subfields": [
          {
            "a": "Thomas, David,"
          },
          {
            "d": "1956-"
          }
        ],
        "ind2": " "
      }
    }
  ]
}
```

If you want to parse a file of MARCJSON records you can:

```python
from pymarc import parse_json_to_array

records = parse_json_to_array(open('test/batch.json'))

print(records[0])
```

```
=LDR  00925njm  22002777a 4500
=001  5637241
=003  DLC
=005  19920826084036.0
=007  sdubumennmplu
=008  910926s1957\\\\nyuuun\\\\\\\\\\\\\\eng\\
=010  \\$a   91758335
=028  00$a1259$bAtlantic
=040  \\$aDLC$cDLC
=050  00$aAtlantic 1259
=245  04$aThe Great Ray Charles$h[sound recording].
=260  \\$aNew York, N.Y. :$bAtlantic,$c[1957?]
=300  \\$a1 sound disc :$banalog, 33 1/3 rpm ;$c12 in.
=511  0\$aRay Charles, piano & celeste.
=505  0\$aThe Ray -- My melancholy baby -- Black coffee -- There's no you -- Doodlin' -- Sweet sixteen bars -- I surrender dear -- Undecided.
=500  \\$aBrief record.
=650  \0$aJazz$y1951-1960.
=650  \0$aPiano with jazz ensemble.
=700  1\$aCharles, Ray,$d1930-$4prf
```

## Developing

If you'd like to further develop pymarc you'll want to get the latest code:

    git clone git://gitlab.com/pymarc/pymarc.git
    cd pymarc
    
Install [uv](https://docs.astral.sh/uv/), and run the tests:

    uv run pytest
    
Run the lint tests:

    uv run ruff check .

Reformat any code that needs it:

    uv run ruff format .
    
And run type checking:

    uv run pyright .

If you want to update the dependencies:

    uv lock --upgrade
    
If you want to build and publish a new version of pymarc on PyPI you can:

    uv build
    uv publish

## Support

The pymarc developers encourage you to join the [pymarc Google
Group](http://groups.google.com/group/pymarc) if you need help.  Also, please
feel free to use [issue tracking](https://gitlab.com/pymarc/pymarc/issues) on
GitLab to submit feature requests or bug reports. If you've got an itch to
scratch, please scratch it, and send merge requests on
[GitLab](http://gitlab.com/pymarc/pymarc).

If you start working with MARC you may feel like you need moral support in
addition to technical support. The #python channel on [code4lib Slack]https://code4lib.org/slack/)
is a good place to start.
