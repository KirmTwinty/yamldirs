# -*- coding: utf-8 -*-
from __future__ import print_function
from contextlib import contextmanager
import os
import shutil
import tempfile
from ruamel.yaml import YAML
import numbers
import datetime

try:                 # pragma: nocover
    from types import NoneType
except ImportError:  # pragma: nocover
    NoneType = type(None)

try:               # pragma: nocover
    basestring
except NameError:  # pragma: nocover
    basestring = (str, bytes)


class YamlDirsException(Exception):
    """Base class for YamlDirs exceptions.
    """


class UnknownType(YamlDirsException):
    """Found a type that we don't know how to handle.
    """


class FilemakerBase(object):
    """Override marked methods to do something useful.  Base class serves as
       a dry-run step generator.
    """

    def __init__(self, root, fdef):
        yaml = YAML(typ='safe')
        self.fdef = yaml.load(fdef)
        self.pushd(root)
        self._make_item(self.fdef)

    def value2str(self, val):
        if isinstance(val, basestring):
            return val
        elif isinstance(val, numbers.Number):
            return str(val)
        elif type(val) == datetime.date:  # datetimes are subclasses of dates.
            return val.isoformat()
        else:
            raise UnknownType("Don't know what to do with %r of type %s" % (
                val, type(val)
            ))

    def _make_item(self, item):
        if isinstance(item, dict):
            return self.make_dict_item(item)
        elif isinstance(item, list):
            return self.make_list_item(item)
        else:
            return self.make_file(
                self.value2str(item), ""
            )

    def make_list_item(self, lst):
        for item in lst:
            self._make_item(item)

    def make_dict_item(self, dct):
        for k, v in dct.items():
            k = self.value2str(k)
            if isinstance(v, (list, dict, NoneType)):
                self.mkdir(k)
                self.pushd(k)
                if v is not None:
                    self._make_item(v)
                self.popd()
            else:
                self.make_file(filename=k, content=self.value2str(v))

    # override the remaining methods.
    def mkdir(self, dirname):  # pragma: nocover
        print("mkdir " + dirname)

    def pushd(self, dirname):  # pragma: nocover
        print("pushd " + dirname)

    def popd(self):  # pragma: nocover
        print("popd")

    def make_file(self, filename, content):  # pragma: nocover
        """Create a new file with name ``filename`` and content ``content``.
           **Must be overridden.**
        """
        print("create file: %s %r" % (filename, content))


class Filemaker(FilemakerBase):
    def __init__(self, root, fdef):
        self._curdir = []
        super(Filemaker, self).__init__(root, fdef)

    def mkdir(self, dirname):
        os.mkdir(dirname)

    def pushd(self, dirname):
        dirname = os.path.abspath(dirname)
        self._curdir.append(os.getcwd())
        os.chdir(dirname)

    def popd(self):
        os.chdir(self._curdir.pop())

    def make_file(self, filename, content):
        """Create a new file with name ``filename`` and content ``content``.
        """
        with open(filename, 'w') as fp:
            fp.write(content)


class FilemakerExplicit(FilemakerBase):
    def __init__(self, root, fdef):
        self._curdir = []
        self.keywords = {
            "mode": self.make_item_mode,
            "user": self.make_item_user,
            "group": self.make_item_group,
        }
        super(FilemakerExplicit, self).__init__(root, fdef)

    def make_dict_item(self, dct):
        if 'directory' in dct or 'file' in dct:
            current = None
            if 'directory' in dct:
                current = dct['directory']
                self.mkdir(dct['directory'])
            elif 'file' in dct:
                current = dct['file']
                content = ""
                if 'content' in dct:
                    content = dct['content']
                self.make_file(dct['file'], content)
            for key in dct:
                if key == 'children':
                    self.pushd(current)
                    self._make_item(dct['children'])
                    self.popd()
                elif key in self.keywords:
                    self.keywords[key](current, dct[key])
        else:
            raise UnknownType("""Don't know what to do with this structure (must
            have `file` or `directory` as key)""")

    def pushd(self, dirname):
        dirname = os.path.abspath(dirname)
        self._curdir.append(os.getcwd())
        os.chdir(dirname)

    def popd(self):
        os.chdir(self._curdir.pop())

    def mkdir(self, dirname):
        os.mkdir(dirname)

    def make_file(self, filename, content):
        """Create a new file with name ``filename`` and content ``content``.
        """
        with open(filename, 'w') as fp:
            fp.write(content)

    def make_item_mode(self, filename, mode):
        """Set the mode of the file ``filename`` to ``mode``.
        """
        try:
           os.chmod(filename, mode)
        except PermissionError:
            print(f"Unable to set the mode {mode} to {filename}.")

    def make_item_user(self, filename, user):
        """Set the user of the current file ``filename`` to ``user``.
         """
        try:
            shutil.chown(filename, user=user)
        except PermissionError:
            print(f"Unable to set the user {user} to {filename}.")

    def make_item_group(self, filename, group):
        """Set the group of the current file ``filename`` to ``group``.
         """
        try:
            shutil.chown(filename, group=group)
        except PermissionError:
            print(f"Unable to set the group {group} to {filename}.")


@contextmanager
def create_files(filedef, cleanup=True):
    """Contextmanager that creates a directory structure from a yaml
       description.
    """
    cwd = os.getcwd()
    tmpdir = os.path.realpath(tempfile.mkdtemp())
    try:
        Filemaker(tmpdir, filedef)
        if not cleanup:  # pragma: nocover
            pass
            # print("TMPDIR =", tmpdir)
        os.chdir(tmpdir)
        yield tmpdir
    finally:
        os.chdir(cwd)
        if cleanup:  # pragma: nocover
            shutil.rmtree(tmpdir, ignore_errors=True)
