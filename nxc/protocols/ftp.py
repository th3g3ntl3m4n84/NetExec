#!/usr/bin/env python3

from nxc.config import process_secret
from nxc.connection import connection
from nxc.helpers.logger import highlight
from nxc.logger import NXCAdapter
from ftplib import FTP


class Ftp(connection):
    def __init__(self, args, db, host):
        self.protocol = "FTP"
        self.remote_version = None

        super().__init__(args, db, host)

    def proto_logger(self):
        self.logger = NXCAdapter(
            extra={
                "protocol": "FTP",
                "host": self.host,
                "port": self.args.port,
                "hostname": self.hostname,
            }
        )

    def proto_flow(self):
        self.proto_logger()
        if self.create_conn_obj():
            if self.enum_host_info():
                if self.print_host_info():
                    if self.login():
                        pass

    def enum_host_info(self):
        welcome = self.conn.getwelcome()
        self.logger.debug(f"Welcome result: {welcome}")
        self.remote_version = welcome.split("220", 1)[1].strip()  # strip out the extra space in the front
        self.logger.debug(f"Remote version: {self.remote_version}")
        return True

    def print_host_info(self):
        self.logger.display(f"Banner: {self.remote_version}")
        return True

    def create_conn_obj(self):
        self.conn = FTP()
        try:
            self.conn.connect(host=self.host, port=self.args.port)
        except Exception as e:
            self.logger.debug(f"Error connecting to FTP host: {e}")
            return False
        return True

    def plaintext_login(self, username, password):
        if not self.conn.sock:
            self.create_conn_obj()
        try:
            self.logger.debug(self.conn.sock)
            resp = self.conn.login(user=username, passwd=password)
            self.logger.debug(f"Response: {resp}")
        except Exception as e:
            self.logger.fail(f"{username}:{process_secret(password)} (Response:{e})")
            self.conn.close()
            return False

        # 230 is "User logged in, proceed" response, ftplib raises an exception on failed login
        if "230" in resp:
            self.logger.debug(f"Host: {self.host} Port: {self.args.port}")
            self.db.add_host(self.host, self.args.port, self.remote_version)

            cred_id = self.db.add_credential(username, password)

            host_id = self.db.get_hosts(self.host)[0].id
            self.db.add_loggedin_relation(cred_id, host_id)

            if username in ["anonymous", ""] and password in ["", "-"]:
                self.logger.success(f"{username}:{process_secret(password)} {highlight('- Anonymous Login!')}")
            else:
                self.logger.success(f"{username}:{process_secret(password)}")

        if self.args.ls:
            files = self.list_directory_full()
            self.logger.display("Directory Listing")
            for file in files:
                self.logger.highlight(file)

        if not self.args.continue_on_success:
            self.conn.close()
            return True
        self.conn.close()

    def list_directory_full(self):
        # in the future we can use mlsd/nlst if we want, but this gives a full output like `ls -la`
        # ftplib's "dir" prints directly to stdout, and "nlst" only returns the folder name, not full details
        files = []
        self.conn.retrlines("LIST", callback=files.append)
        return files

    def supported_commands(self):
        raw_supported_commands = self.conn.sendcmd("HELP")
        supported_commands = [item for sublist in (x.split() for x in raw_supported_commands.split("\n")[1:-1]) for item in sublist]
        self.logger.debug(f"Supported commands: {supported_commands}")
        return supported_commands
