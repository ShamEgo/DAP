# Parallel Coordinates Builder

This is the Data Arena's parallel coordinates builder that was created for use with the DAVM.
Its a python script that uses a parallel coordinates web page created by Kai Chang as a template and places the given csv data into the json data file.

## Running `build.py`

It can be run like this:

```
./build.py Public.csv Institution name
```

Where `Public.csv` is the data file, `Institution` is the column to group items by, and subsequent arguments are the column names to omit generating axes for. If the column name has spaces, the argument should be enclosed in quotes `'Like this'`.

The files are created in a directory named after the csv file - in this case `Public`.

The generated web page can be viewed when launched from a local web server, such as the one launched with python:

```
~/Builder $ cd Public
~/Builder/Public $ python -m http.server
Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/) ...
```
And accessing the page from http://localhost:8000 in your web browser.

## More information
More info about Parallel Coordinates and this implementation can be found here: 

https://syntagmatic.github.io/parallel-coordinates/
https://github.com/syntagmatic/parallel-coordinates