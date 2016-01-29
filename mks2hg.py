from Commander      import Commander
from itertools      import imap, ifilter
from sets           import Set
from datetime       import datetime
from sys            import argv
import os

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
    def __init__(self, mks, ctime, prj, name, rev):
        super(Member, self).__init__()
        self.mks        = mks
        self.ctime      = ctime #ugly, cp closed date.
        self.prj        = prj
        self.name       = name.strip()
        self.rev        = rev.strip()

    # get content of the member
    def sview(self):
        options = { 'revision' : self.rev,
                    'project'  : self.prj }
        out = self.mks.viewrevision(self.name, **options)
        return out

    def view(self):
        if len(self.prj.history) == 0:
            try:
                return self.sview()
            except:
                pass

        # find proper project revision related.
        options = { 'revision'          : self.rev,
                    'projectRevision'   : self.prj.get_revision_after(self.ctime),
                    'project'           : self.prj }
        try:
            return self.mks.viewrevision(self.name, **options)
        except Exception as e:
            alias = self.prj.get_member_alias(self.name)
            for alias_name in alias:
                try:
                    return self.mks.viewrevision(alias_name, **options)
                except Exception as et:
                    print "= Error: unable to view file %s at revision %s: %s" % (self.name, self.rev, et)
                    pass
            raise e

    # save to specified path.
    def saveas(self, path):
        print "= Info: Saving file %s" % path
        try:
            if not os.path.exists(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path))
            out = self.view()
            with open(path, 'wb') as f:
                f.write(out)
        except Exception as e:
            print "= Error: unable to save file %s, %s" %(path, e)
            pass

# Abstract action class
class Action(object):
    def __init__(self, mks, ctime, fname, rev, project):
        super(Action, self).__init__()
        self.mks        = mks
        self.ctime      = ctime
        self.fname      = fname
        self.rev        = rev
        self.project    = project

    def __str__(self):
        return str((self.__class__, self.fname, self.rev, str(self.project)))

    # abstract method.
    def update_fs(self, prj):
        pass

    def get_path(self, root_project, root_dpath):
        if self.project.is_subprj(root_project):
            return root_dpath + self.project.path[len(root_project.path[:-10]) : -10]
        return None

    def apply_change(self, prj, path):
        subpath = self.get_path(prj, path)
        if subpath != None:
            self.make_change(subpath)

    # abstract method.
    def make_change(self, subpath):
        raise NotImplementedError("Must override methodB")

#''' Add File ''' && ''' Update File '''
class ActionUpdate(Action):
    def make_change(self, subpath):
        mem = Member(self.mks, self.ctime, self.project, self.fname, self.rev)
        mem.saveas(subpath + self.fname)

#''' Rename File '''
class ActionRename(Action):
    def parse_name(self):
        # "name (nameb)"
        bl  = self.fname.index('(')
        br  = self.fname.rindex(')')
        return (self.fname[bl+1:br], self.fname[:bl-1])

    def make_change(self, subpath):
        src, dst = self.parse_name()
        dst = subpath + dst
        src = subpath + src
        # in case dst already there,
        # it means the wrong order of actions
        # in change package
        # so we just delete the src file.
        print "= Info: Rename file from %s to %s" % (src, dst)
        if os.path.exists(dst):
            # windows isn't case sensitive
            if src.upper() != dst.upper():
                os.remove(src)
        else:
            os.rename(src, dst)

    def update_fs(self, prj):
        if self.project.is_subprj(prj):
            src, dst = self.parse_name()
            self.project.rename_member(src, dst)

#''' Drop File '''
class ActionDrop(Action):
    def make_change(self, subpath):
        try:
            os.remove(subpath + self.fname)
        except Exception as e:
            print "= Error: unable delete file %s: %s" %(subpath + self.fname, e)

#''' Create Subproject '''
class ActionCreateSubPrj(Action):
    def make_change(self, subpath):
        dpath = subpath + self.fname[:self.fname.rindex("project.pj")]
        try:
            os.mkdir(dpath)
        except Exception as e:
            print "= Error: unable mkdir %s: %s" % (dpath, e)
            print "= Error: use makedirs instead!"
            os.makedirs(dpath)

#''' Drop Subproject '''
class ActionDropSubPrj(Action):
    def make_change(self, subpath):
        os.rmdir(subpath + self.fname[:self.fname.rindex("project.pj")])

#''' Supported actions in Change Package '''
dict_str_class = { 'Add'                : ActionUpdate,
                   'Add From Archive'   : ActionUpdate,         # extra
                   'Create Subproject'  : ActionCreateSubPrj,
                   'Add Subproject'     : ActionCreateSubPrj,   # extra
                   'Update'             : ActionUpdate,
                   'Update Revision'    : ActionUpdate,         # extra
                   'Rename'             : ActionRename,
                   'Drop'               : ActionDrop,
                   'Drop Subproject'    : ActionDropSubPrj }

class ChangePackage(object):
    def __init__(self, mks, id, viewinfo=False):
        super(ChangePackage, self).__init__()
        self.mks     = mks
        self.id      = id.strip()
        self.actions = []
        self.info    = None
        if viewinfo:
            self.view()

    def __str__(self):
        s = self.id + ':\n'
        if self.info != None:
            for k, v in self.info.iteritems():
                s += '%s : %s' % (k, v)
        for a in self.actions:
            s += str(a) + '\n'
        return s

    def add_change(self, action, fname, revision, prj_path, ctime):
        if action in dict_str_class:
            self.actions.append(dict_str_class[action](self.mks, ctime, fname, revision, mks_get_project(self.mks, prj_path)))
        else:
            print "= Error: Unkown action", action

    def view(self):
        options = {'noshowReviewLog'        : True,
                   'noshowPropagationInfo'  : True}
        out = self.mks.viewcp(self.id, **options)
        print out
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
                action = line.strip().split('\t')
                if len(action) < 5:
                    continue
                self.add_change(action[0], action[2], action[3], action[4], ctime)

    def apply_change(self, prj, dest):
        for act in self.actions:
            act.apply_change(prj, dest+'/')

    def update_fs(self, prj):
        for act in self.actions:
            act.update_fs(prj)

class Project(object):

    def __init__(self, mks, path, bHistory=False):
        super(Project, self).__init__()
        self.mks         = mks
        self.path        = path.strip()
        self.history     = []
        self.renames     = [] # rude way to deal with renamed file
        if bHistory:
            viewhistory()

    def __str__(self):
        return self.path

    def rename_member(self, src, dst):
        self.renames.append((src, dst))

    def get_member_alias(self, src):
        r = filter(lambda x : x[0] == src, self.renames)
        return map(lambda x : x[1], r)

    def get_revision_after(self, time):
        self.viewhistory()
        prj_rev = next(r for (r, t) in reversed(self.history) if t > time)
        if prj_rev == None:
            raise Exception("Unable to find project revision")
        return prj_rev

    # get list cp for current project
    def rlog(self, onlyClosed=True):
        options = { 'noheaderformat'  : True,
                    'noTrailerFormat' : True,
                    'fields'          : 'cpid',
                    'rfilter'         : 'branch::current',
                    'recurse'         : True,
                    'project'         : self.path }
        print "= Info: fetching project log (%s)..." % self.path
        out = self.mks.rlog(**options)
        # drop empty line
        lines = filter(lambda x: x!= "", out.splitlines())
        # sort change package.
        cps = map(lambda id : ChangePackage(self.mks, id, viewinfo=True), sorted(set(lines)))
        if onlyClosed:
            return sorted(filter(lambda x : x.info != None and x.info['closeddate'] != None, cps), key=lambda x : x.info['closeddate'])
        else:
            return cps

    def viewhistory(self):
        if len(self.history) != 0:
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
            self.history.append((rev, parse_time(stime)))

    def is_subprj(self, prj):
        return self.path.startswith(prj.path[:-10])

def hg_commit(hg, path, cp):
    os.chdir(path)
    options = { 'A'         : True,
                'message'   : '[' + cp.id + ']' + cp.info['summary'],
                'user'      : cp.info['author'],
                'date'      : cp.info['closeddate'].strftime("%Y-%m-%d %H:%M:%S")}
    try:
        hg.commit(**options)
    except Exception as e:
        print "= Error: unable to commit cp(%s): %s" % (cp.id, e)
        print "= Error: ignore error!"

def mks2hg(prj_path, dest):
    mks = Commander('si', '=')
    hg  = Commander('hg', ' ')
    prj = mks_get_project(mks, prj_path)
    cps = prj.rlog()
    hg.init(dest)
    for cp in cps:
        #print cp
        cp.update_fs(prj)
    for cp in cps:
        print cp
        cp.apply_change(prj, dest)
        hg_commit(hg, dest, cp)

if __name__ == '__main__':
    if len(argv) != 3:
        print "Help: %s project directory" % argv[0]
        exit(1)
    mks2hg(argv[1], argv[2])
