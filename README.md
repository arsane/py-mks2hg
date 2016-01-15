### py-mks2hg
A python based tool for importing source code from MKS to Mercurial. (Tested on MKS client 2009)

Feature supported:
- able to retrieve change packages base on project.
- load change packages into Mercurial as commits with proper change package information.

Problem:
- Shared project not supported yet.
- Some file deleted within same project version can't retrieve because of MKS's ability.
- File rename not case sensitive. (Windows limits)
- Multiple revision in same MKS change package, only the latest revision will in Mercurial's commit.

### Requirement
- Python 2.7
- MKS on Windows
- Mercurial on Windows

### Usage.
1. connect/authenticate MKS with MKS client.
2. run tool with specifying:
  - project url to import to Mercurial
  - local directory to save Mercurial repository.
  

