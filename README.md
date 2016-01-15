# py-mks2hg
A python based tool for importing source code from MKS to Mercurial

Feature supported:
- able to retrieve change packages base on project.
- load change packages into Mercurial as commits with proper change package information.

Problem:
- Shared project not supported yet.
- Some file deleted within same project version can't retrieve.
- file rename not case sensitive. (Windows limits)

# Requirement
- Python 2.7
- MKS on Windows
- Mercurial on Windows

# Usage.
1. connect/authenticate MKS with MKS tool
2. run tool with specifying:
  - project url to import to Mercurial
  - local directory to save Mercurial repository.
  

