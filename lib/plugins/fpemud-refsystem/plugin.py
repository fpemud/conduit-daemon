#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import time
import socket
import subprocess


class DataProviderPrivateData:

    def __init__(self):
        self._portageCfgDir = "/etc/portage"
        self._makeConf = os.path.join(self._portageCfgDir, "make.conf")
        self._portageDataDir = "/var/lib/portage"
        self._overlayDir = os.path.join(self._portageDataDir, "overlay-fpemud-private")
        self._overlayRealDir = os.path.join(self._portageDataDir, "laymanfiles", "fpemud-private")
        self._distfilesDir = os.path.join(self._portageDataDir, "distfiles-private")

        self._api = None
        self._cfgFile = None
        self._lockFile = None
        self._logFile = None
        self._port = None
        self._proc = None

    def activate(self, api):
        # check fpemud-refsystem
        if not os.path.exists(os.path.dirname(self._portageDataDir)):
            raise Exception("not fpemud-refsystem")

        # create private overlay
        if True:
            # create real overlay directory
            _Util.repoMkDir(self._overlayRealDir, "fpemud-overlay-private")

            # create overlay directory
            if not os.path.exists(self._overlayRealDir):
                _Util.ensureDir(os.path.dirname(self._overlayDir))
                _Util.shellCall("/bin/ln -sf laymanfiles/fpemud-private %s" % (self._overlayRealDir))

            # create repo file
            fullfn, buf = _Util.generateOverlayReposConfFile(self._portageCfgDir, "overlay-fpemud-private",
                                                             self._overlayRealDir, "fpemud-overlay-private")
            _Util.checkAndFixFile(fullfn, buf)

        # create private distfiles directory
        if True:
            # create distfiles directory
            _Util.ensureDir(self._distfilesDir)

            # modify make.conf
            dirList = _Util.getMakeConfVar(self._makeConf, "PORTAGE_RO_DISTDIRS").split(" "):
            if self._distfilesDir not in dirList:
                dirList.append(self._distfilesDir)
                _Util.setMakeConfVar(self._makeConf, "PORTAGE_RO_DISTDIRS", " ".join(dirList))

    def deactivate(self):
        pass

    def start_accept_get(self, api):
        ret = []
        try:
            self._api = api
            self._cfgFile = os.path.join(self._api.get_tmp_dir(), "rsync.cfg")
            self._lockFile = os.path.join(self._api.get_tmp_dir(), "rsync.lock")
            self._logFile = os.path.join(self._api.get_log_dir(), "rsync.log")

            self._port = _Util.getFreeTcpPort()
            ret.append(self._port)

            buf = ""
            buf += "lock file = %s\n" % (self._lockFile)
            buf += "log file = %s\n" % (self._logFile)
            buf += "\n"
            buf += "port = %s\n" % (self._port)
            buf += "max connections = 1\n"
            buf += "timeout = 600\n"
            buf += "hosts allow = %s\n" % (self._api.get_peer_ip())
            buf += "\n"
            buf += "use chroot = yes\n"
            buf += "uid = root\n"
            buf += "gid = root\n"
            buf += "\n"
            if os.path.exists(self._overlayRealDir):
                ret.append("overlay")
                buf += "[overlay]\n"
                buf += "path = %s\n" % (self._overlayRealDir)
                buf += "read only = yes\n"
                buf += "\n"
            if os.path.exists(self._distfilesDir):
                ret.append("distfiles")
                buf += "[distfiles]\n"
                buf += "path = %s\n" % (self._distfilesDir)
                buf += "read only = yes\n"
                buf += "\n"
            with open(self._cfgFile, "w") as f:
                f.write(buf)

            cmd = "/usr/bin/rsync --daemon --no-detach --config=\"%s\"" % (self._cfgFile)
            self._proc = subprocess.Popen(cmd, shell=True, universal_newlines=True)

            return ret
        except:
            self.stop_accept_get()
            raise

    def stop_accept_get(self):
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait()
            self._proc = None
        self._port = None
        self._logFile = None
        if self._lockFile is not None:
            os.unlink(self._lockFile)
            self._lockFile = None
        if self._cfgFile is not None:
            os.unlink(self._cfgFile)
            self._cfgFile = None
        self._api = None

    def get(self, api, peer_data):
        logFile = os.path.join(api.get_log_dir(), "rsync.log")
        port = peer_data[0]

        if "overlay" in peer_data:
            # sync real overlay directory
            _Util.ensureDir(os.path.dirname(self._overlayRealDir))
            url = "rsync://%s:%d/overlay" % (api.get_peer_ip(), port)
            cmd = "/usr/bin/rsync -a -z --delete %s %s >%s 2>&1" % (url, self._overlayRealDir, logFile)
            _Util.shellCall(cmd)

            # sync real overlay directory
            _Util.ensureDir(os.path.dirname(self._overlayDir))
            _Util.shellCall("/bin/ln -sf laymanfiles/fpemud-private %s" % (self._overlayRealDir))

            # create repo file
            _Util.ensureDir(os.path.dirname(self._repoFile))
            with open(self._repoFile, "w") as f:
                buf = ""
                buf += "[fpemud-private]\n"
                buf += "auto-sync = no\n"
                buf += "location = %s\n" % (self._overlayDir)
                f.write(buf)

        if "distfiles" in peer_data:
            # sync distfiles directory
            _Util.ensureDir(os.path.dirname(self._distfilesDir))
            url = "rsync://%s:%d/distfiles" % (api.get_peer_ip(), port)
            cmd = "/usr/bin/rsync -a -z --delete %s %s >%s 2>&1" % (url, self._distfilesDir, logFile)
            _Util.shellCall(cmd)

            # modify make.conf
            pass


class _Util:

    @staticmethod
    def ensureDir(dirname):
        if not os.path.exists(dirname):
            os.makedirs(dirname)

    @staticmethod
    def repoMkDir(repoDir, repoName):
        """Example: repoDir = /var/lib/portage/repo-fpemud-overlay
                    repoName = repo-fpemud-overlay"""

        assert not os.path.exists(repoDir)
        os.mkdir(repoDir)
        os.mkdir(os.path.join(repoDir, "metadata"))
        with open(os.path.join(repoDir, "metadata", "layout.conf"), "w") as f:
            f.write("masters = gentoo\n")
            f.write("thin-manifests = true\n")
        os.mkdir(os.path.join(repoDir, "profiles"))
        with open(os.path.join(repoDir, "profiles", "repo_name"), "w") as f:
            f.write(repoName)

    @staticmethod
    def generateOverlayReposConfFile(portageCfgReposDir, repoName, repoDir, innerRepoName):
        buf = ""
        buf += "[%s]\n" % (innerRepoName)
        buf += "auto-sync = no\n"
        buf += "priority = %d\n" % (5000)
        buf += "location = %s\n" % (repoDir)

        fullfn = os.path.join(portageCfgReposDir, "overlay-%s.conf" % (repoName))
        return (fullfn, buf)

    @staticmethod
    def checkAndFixFile(filename, content):
        if os.path.exists(filename):
            with open(filename, "r") as f:
                if f.read() == content:
                    return

        with open(filename, "w") as f:
            f.write(content)

    @staticmethod
    def getFreeTcpPort(start_port=10000, end_port=65536):
        for port in range(start_port, end_port):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.bind((('', port)))
                return port
            except socket.error:
                continue
            finally:
                s.close()
        raise Exception("No valid tcp port in [%d,%d]." % (start_port, end_port))

    @staticmethod
    def shellCall(cmd):
        # call command with shell to execute backstage job
        # scenarios are the same as FmUtil.cmdCall

        ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             shell=True, universal_newlines=True)
        if ret.returncode > 128:
            # for scenario 1, caller's signal handler has the oppotunity to get executed during sleep
            time.sleep(1.0)
        if ret.returncode != 0:
            ret.check_returncode()
        return ret.stdout.rstrip()

    @staticmethod
    def getMakeConfVar(makeConfFile, varName):
        """Returns variable value, returns "" when not found
           Multiline variable definition is not supported yet"""

        buf = ""
        with open(makeConfFile, 'r') as f:
            buf = f.read()

        m = re.search("^%s=\"(.*)\"$" % (varName), buf, re.MULTILINE)
        if m is None:
            return ""
        varVal = m.group(1)

        while True:
            m = re.search("\\${(\\S+)?}", varVal)
            if m is None:
                break
            varName2 = m.group(1)
            varVal2 = FmUtil.getMakeConfVar(makeConfFile, varName2)
            if varVal2 is None:
                varVal2 = ""

            varVal = varVal.replace(m.group(0), varVal2)

        return varVal

    @staticmethod
    def setMakeConfVar(makeConfFile, varName, varValue):
        """Create or set variable in make.conf
           Multiline variable definition is not supported yet"""

        endEnter = False
        buf = ""
        with open(makeConfFile, 'r') as f:
            buf = f.read()
            if buf[-1] == "\n":
                endEnter = True

        m = re.search("^%s=\"(.*)\"$" % (varName), buf, re.MULTILINE)
        if m is not None:
            newLine = "%s=\"%s\"" % (varName, varValue)
            buf = buf.replace(m.group(0), newLine)
            with open(makeConfFile, 'w') as f:
                f.write(buf)
        else:
            with open(makeConfFile, 'a') as f:
                if not endEnter:
                    f.write("\n")
                f.write("%s=\"%s\"\n" % (varName, varValue))
