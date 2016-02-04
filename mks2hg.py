from itertools      import imap, ifilter
from sets           import Set
from datetime       import datetime
from optparse       import OptionParser
from Commander      import Commander
import os, errno, shutil, logging

def parse_time(stime):
    try:
        return datetime.strptime(stime.strip(), "%b %d, %Y %I:%M:%S %p")
    except ValueError:
        return None

# simple project cache wrapper.
g_prj_cache = {}
def mks_get_project(mks, ppath):
    if ppath not in g_prj_cache:
        g_prj_cache[ppath] = Project(mks, ppath)
    return  g_prj_cache[ppath]

class Member(object):
    def __init__(self, mks, time, prj, name, rev):
        self.mks        = mks
        self.prj        = prj
        self.name       = name.strip()
        self.rev        = rev.strip()
        self.time       = time

    # get content of the member
    def read_fast(self):
        options = { 'revision' : self.rev,
                    'project'  : self.prj }
        return self.mks.viewrevision(self.name, **options)

    def read(self):
        # 1. get file without specify revision.
        if len(self.prj.revisions) == 0:
            try:
                return self.read_fast()
            except:
                pass

        # 2. read by specify project revision
        options = { 'revision'          : self.rev,
                    'projectRevision'   : self.prj.get_revision_after(self.time),
                    'project'           : self.prj }
        try:
            return self.mks.viewrevision(self.name, **options)
        except:
            pass

        # 3. get file by other file name in case the file was renamed.
        for alias, ctime in self.prj.get_member_alias(self.name):
            try:
                options['projectRevision'] = self.prj.get_revision_after(ctime)
                return self.mks.viewrevision(alias, **options)
            except:
                pass

        # 4. raise exception after all the fails
        raise Exception("Unable to read file")

    # save to specified path.
    def save(self, fpath):
        logging.debug("Saving file(rev : %s) %s" % (self.rev, fpath))
        try:
            if not os.path.exists(os.path.dirname(fpath)):
                os.makedirs(os.path.dirname(fpath))
            # may fail becoz of revision lost.
            out = self.read()
            with open(fpath, 'wb') as f:
                f.write(out)
        except Exception as e:
            logging.warn("unable to save file %s, %s" %(fpath, e))

# Abstract change class
class Change(object):
    def __init__(self, mks, desc, ctime, fname, rev, prj):
        self.mks        = mks
        self.desc       = desc
        self.ctime      = ctime
        self.fname      = fname
        self.rev        = rev
        self.prj        = prj

    def __str__(self):
        return "(%-18s, %-30s, %-8s, %s )" % (self.desc, self.fname, self.rev, str(self.prj))

    # abstract method.
    def update_fs(self, root_prj):
        pass

    def get_project_dir(self, root_prj, root_dir):
        if self.prj in root_prj:
            return root_dir + self.prj.path[len(root_prj.path[:-10]) : -10]
        return None

    def apply_change(self, root_prj, root_dir):
        prj_dir = self.get_project_dir(root_prj, root_dir)
        if prj_dir != None:
            self.make_change(prj_dir)
            return True
        return False

    # abstract method.
    def make_change(self, prj_dir):
        raise NotImplementedError("Must override method")

#''' Add File ''' && ''' Update File '''
class FileUpdate(Change):
    def make_change(self, prj_dir):
        mem = Member(self.mks, self.ctime, self.prj, self.fname, self.rev)
        mem.save(prj_dir + self.fname)

#''' Rename File '''
class FileRename(Change):
    def parse_name(self):
        # "name (nameb)"
        bl  = self.fname.index('(')
        br  = self.fname.rindex(')')
        return (self.fname[bl+1:br], self.fname[:bl-1])

    def make_change(self, prj_dir):
        src, dst = self.parse_name()
        src = prj_dir + src
        dst = prj_dir + dst
        # in case dst already there,
        # it means the wrong order of changes
        # in change package
        # so we just delete the src file.
        logging.debug("Rename file from %s to %s" % (src, dst))
        if os.path.exists(dst):
            # windows isn't case sensitive
            if src.upper() != dst.upper():
                os.remove(src)
        else:
            os.rename(src, dst)

    def update_fs(self, root_prj):
        if self.prj in root_prj:
            src, dst = self.parse_name()
            self.prj.rename_member(src, dst, self.ctime)

#''' Drop File '''
class FileDrop(Change):
    def make_change(self, prj_dir):
        try:
            os.remove(prj_dir + self.fname)
        except Exception as e:
            logging.warn("Unable delete file %s: %s" %(prj_dir + self.fname, e))

#''' Create Subproject '''
class ProjectCreate(Change):
    def make_change(self, prj_dir):
        dpath = prj_dir + self.fname[:self.fname.rindex("project.pj")]
        if not os.path.exists(dpath):
            try:
                os.mkdir(dpath)
            except Exception as e:
                logging.warn("Unable mkdir %s: %s" % (dpath, e))
                logging.warn("Use makedirs instead!")
                os.makedirs(dpath)

#''' Drop Subproject '''
class ProjectDrop(Change):
    def make_change(self, prj_dir):
        dpath = prj_dir + self.fname[:self.fname.rindex("project.pj")]
        try:
            os.rmdir(dpath)
        except OSError as e:
            if e.errno != errno.ENOENT:
                shutil.rmtree(dpath)

#''' Supported changes in Change Package '''
dict_str_class = { 'Add'                : FileUpdate,
                   'Add From Archive'   : FileUpdate,       # extra
                   'Create Subproject'  : ProjectCreate,
                   'Add Subproject'     : ProjectCreate,    # extra
                   'Update'             : FileUpdate,
                   'Update Revision'    : FileUpdate,       # extra
                   'Rename'             : FileRename,
                   'Drop'               : FileDrop,
                   'Drop Subproject'    : ProjectDrop }

class ChangePackage(object):
    def __init__(self, mks, id, viewinfo=True):
        self.mks     = mks
        self.id      = id.strip()
        self.changes = []
        self.info    = None
        if viewinfo:
            self.view()

    def __str__(self):
        s = '\n[' + self.id + ']\n'
        if self.info != None:
            for k, v in self.info.iteritems():
                s += '(%-18s: %s)\n' % (k, v)
        for a in self.changes:
            s += str(a) + '\n'
        return s

    def add_change(self, change, fname, revision, prj_path, ctime):
        if change in dict_str_class:
            self.changes.append(dict_str_class[change](self.mks, change, ctime,
                                                       fname, revision,
                                                       mks_get_project(self.mks, prj_path)))
        else:
            logging.error("Unknown change '%s' in cp %s" % (change, self.id))

    def is_closed(self):
        return self.info != None and self.info['closeddate'] != None

    def view(self):
        options = {'noshowReviewLog'        : True,
                   'noshowPropagationInfo'  : True}
        out = self.mks.viewcp(self.id, **options)
        logging.debug('\n' + out)
        lines = out.splitlines()
        _, summary = lines[0].split('\t', 1)           # summary
        author, _, stime, _ = lines[1].split('\t', 3)  # author and closed time
        # ignore pending cp.
        if stime[:6] != 'Closed':
            return
        ctime = parse_time(stime[8:][:-1])
        self.info = {'author'       : author,
                     'summary'      : summary,
                     'closeddate'   : ctime }
        for line in lines[2:]:
            if len(line) != 0:
                change = line.strip().split('\t')
                if len(change) < 5:
                    continue
                self.add_change(change[0], change[2], change[3], change[4], ctime)

    def apply_change(self, prj, dest):
        return all( change.apply_change(prj, dest) for change in self.changes )

    def update_fs(self, prj):
        for act in self.changes:
            act.update_fs(prj)

class Project(object):
    def __init__(self, mks, path):
        self.mks         = mks
        self.path        = path.strip()
        self.revisions   = []
        self.renames     = []

    def __str__(self):
        return self.path

    def rename_member(self, src, dst, ctime):
        self.renames.append((src, dst, ctime))

    def get_member_alias(self, src):
        r = filter(lambda x : x[0] == src, self.renames)
        alias = map(lambda x : (x[1], x[2]), r)
        # recursively get all alias
        return alias + reduce(lambda x, y : x + y, map(lambda x : self.get_member_alias(x[0]), alias), [])

    def get_revision_after(self, time):
        self.__get_revisions()
        prj_rev = next(r for (r, t) in reversed(self.revisions) if t > time)
        if prj_rev == None:
            raise Exception("Unable to find project revision")
        return prj_rev

    # get list cp for current project
    def get_changepackages(self, id_filter):
        options = { 'noheaderformat'  : True,
                    'noTrailerFormat' : True,
                    'fields'          : 'cpid',
                    'rfilter'         : 'branch::current',
                    'recurse'         : True,
                    'project'         : self.path }
        logging.info("Fetching change package ids on (%s)..." % self.path)
        out = self.mks.rlog(**options)

        # drop empty line
        lines = filter(lambda x: x!= "" and (id_filter == None or id_filter(x)), set(out.splitlines()))

        logging.info("Get details info for %d change packages" % len(lines))
        # sort change package.
        cps = map(lambda id : ChangePackage(self.mks, id), sorted(lines))

        # only return closed cp.
        return sorted(filter(lambda x : x.is_closed(), cps), key=lambda x : x.info['closeddate'])

    def __get_revisions(self):
        if len(self.revisions) != 0:
            return

        options = { 'rfilter'         : 'branch::current',
                    'fields'          : 'revision,date',
                    'projectRevision' : '1.1',
                    'project'         : self.path }
        out = self.mks.viewprojecthistory(**options)
        lines = filter(lambda x: x!= "", out.splitlines())

        # ignore first line for project path
        for line in lines[1:]:
            rev, stime = line.strip().split('\t')
            self.revisions.append((rev, parse_time(stime)))

    def __contains__(self, prj):
        return prj.path.startswith(self.path[:-10])

def hg_commit(hg, path, cp):
    os.chdir(path)
    options = { 'A'         : True,
                'message'   : '[' + cp.id + ']' + cp.info['summary'],
                'user'      : cp.info['author'],
                'date'      : cp.info['closeddate'].strftime("%Y-%m-%d %H:%M:%S")}
    try:
        hg.commit(**options)
    except Exception as e:
        logging.warn("Unable to commit cp(%s): %s" % (cp.id, e))

def hg_get_commited_cps(hg, path):
    os.chdir(path)
    options = { 'template' : '{desc}\\n' }
    out = hg.log(**options)
    cps = []
    for line in out.splitlines():
        try:
            li = line.index('[')
            ri = line.index(']')
            if li == 0:
                cps.append(line[li+1:ri])
        except:
            pass
    return set(cps)

def mks2hg(prj_path, root_dir):
    mks = Commander('si', '=')
    hg  = Commander('hg', ' ')
    root_prj = mks_get_project(mks, prj_path)

    # if hg already created, working on resync mode
    cp_syned = []
    if os.path.exists(root_dir + '.hg'):
        cp_syned = hg_get_commited_cps(hg, root_dir)
    else:
        hg.init(root_dir)

    # retrieve list of cp to sync.
    cps = root_prj.get_changepackages(lambda id : id not in set(cp_syned))

    # sync change packages.
    for cp in cps:
        cp.update_fs(root_prj)

    logging.info("Applying change packages...")
    for cp in cps:
        logging.debug(cp)
        if cp.apply_change(root_prj, root_dir):
            hg_commit(hg, root_dir, cp)
        else:
            logging.debug("Ignore cp %s)" % cp.id)

if __name__ == '__main__':
    usage = "usage: %prog [options] project directory"
    parser = OptionParser(usage=usage, version="%prog 1.0")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=True,
                      help="print status message to stdout [default]")
    parser.add_option("-q", "--quiet",
                      action="store_false", dest="verbose",
                      help="disable status message")
    (options, args) = parser.parse_args()
    if options.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    mks2hg(args[0], args[1] + '/')
