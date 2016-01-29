### py-mks2hg
A python based tool for importing source code from MKS to Mercurial. (Tested on MKS client 2009)

Feature supported:
- able to retrieve change packages base on project.
- load change packages into Mercurial as commits with proper change package information.

Problems:
- Shared project not supported yet.
- So far only change package on main branch is imported.
- Some file deleted within same project version can't retrieve because of MKS's ability.
- File rename not case sensitive. (Windows limits)
- Multiple revision in same MKS change package, only the latest revision will in Mercurial's commit.

### Requirement
- Tested with Python 2.7
- MKS on Windows and MKS command line in path environment variable.
- Mercurial on Windows and command in path environment variable.

### Usage.
1. connect/authenticate MKS with MKS client (no authentication in tool).
2. run tool with specifying arguments:
  - project url to import to Mercurial
  - local directory to save Mercurial repository.
  

