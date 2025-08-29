# Copyright (c) 2017, Frappe and contributors
# For license information, please see license.txt


import json
import os
import re
import shlex
import subprocess
import time
from subprocess import PIPE, Popen, check_output, run

import frappe
import pymysql
from frappe.model.document import Document

from bench_manager.bench_manager.doctype.bench_settings.bench_settings import sync_sites
from bench_manager.bench_manager.utils import (
	safe_decode,
	verify_whitelisted_call,
)


class Site(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		app_list: DF.Text | None
		auto_backup: DF.Check
		backup_limit: DF.Int
		backup_size: DF.Float
		bench_settings: DF.Data | None
		database_size: DF.Float
		db_name: DF.Data | None
		db_password: DF.Password | None
		developer_flag: DF.Int
		developer_mode: DF.Check
		disable_website_cache: DF.Check
		dropbox_backup: DF.Check
		emails: DF.Data | None
		expiry: DF.Data | None
		files_size: DF.Float
		install_erpnext: DF.Check
		maintenance_mode: DF.Check
		pause_scheduler: DF.Check
		site_alias: DF.Text | None
		site_name: DF.Data
		space: DF.Data | None
		total: DF.Float
	# end: auto-generated types
	site_config_fields = (
		"maintenance_mode",
		"pause_scheduler",
		"db_name",
		"db_password",
		"developer_mode",
		"disable_website_cache",
		"limits",
	)
	limits_fields = ("emails", "expiry", "space", "space_usage")
	space_usage_fields = ("backup_size", "database_size", "files_size", "total")

	def get_attr(self, varname):
		return getattr(self, varname)

	def set_attr(self, varname, varval):
		return setattr(self, varname, varval)

	def validate(self):
		self.update_configs()
		self.sync_configs()

	def on_update(self):
		commands = []
		if self.auto_backup:
			commands.append(
				f"bench --site {self.site_name} execute frappe.db.set_single_value --args \"['System Settings','backup_limit',{self.backup_limit}]\""
			)

		if len(commands) > 0:
			timestamp = frappe.utils.now()
			frappe.enqueue(
				"bench_manager.bench_manager.utils.run_command",
				commands=commands,
				doctype=self.doctype,
				timestamp=timestamp,
				docname=self.name,
			)

	def after_command(self, commands=None):
		frappe.publish_realtime("Bench-Manager:reload-page")
		pass

	@frappe.whitelist()
	def update_app_alias(self):
		self.update_app_list()
		self.update_site_alias()

	def update_app_list(self):
		# self.set_attr("app_list", '\n'.join(self.get_installed_apps()))
		self.db_set("app_list", "\n".join(self.get_installed_apps()))

	def update_site_alias(self):
		alias_list = ""
		for link in os.listdir("."):
			if os.path.islink(link) and self.name in os.path.realpath(link):
				alias_list += link + "\n"
		self.db_set("site_alias", alias_list)

	def get_installed_apps(self):
		all_sites = safe_decode(check_output("ls")).strip("\n").split("\n")

		if self.site_name not in all_sites:
			list_apps = "frappe"
		else:
			list_apps = check_output(
				shlex.split(f"bench --site {self.site_name} list-apps"),
				cwd="..",
			)

		if "frappe" not in safe_decode(list_apps):
			list_apps = "frappe"
		return safe_decode(list_apps).strip("\n").split("\n")

	def update_configs(self):
		from bench_manager.bench_manager.utils import update_site_config

		EDITABLE_SITE_CONFIG_FIELDS = (
			"maintenance_mode",
			"pause_scheduler",
			"developer_mode",
			"disable_website_cache",
		)

		for field in EDITABLE_SITE_CONFIG_FIELDS:
			value = str(self.get(field, 0))
			update_site_config(field, value, self.site_name)

	def sync_configs(self):
		config = frappe.get_site_config(site_path=os.path.join(os.getcwd(), self.site_name))
		for field in self.site_config_fields:
			value = config.get(field)
			self.set(field, value)

	@frappe.whitelist()
	def create_alias(self, timestamp, alias):
		files = check_output("ls")
		if alias in files:
			frappe.throw("Sitename already exists")
		else:
			self.console_command(timestamp=timestamp, caller="create-alias", alias=alias)

	@frappe.whitelist()
	def console_command(
		self, timestamp, caller, alias=None, app_name=None, admin_password=None, mysql_password=None
	):
		site_abspath = None
		if alias:
			site_abspath = os.path.abspath(os.path.join(self.name))
		commands = {
			"migrate": [f"bench --site {self.name} migrate"],
			"create-alias": [f"ln -s {site_abspath} sites/{alias}"],
			"delete-alias": [f"rm sites/{alias}"],
			"backup": [f"bench --site {self.name} backup --with-files"],
			"reinstall": [f"bench --site {self.name} reinstall --yes --admin-password {admin_password}"],
			"install_app": [f"bench --site {self.name} install-app {app_name}"],
			"uninstall_app": [f"bench --site {self.name} uninstall-app {app_name} --yes"],
			"drop_site": [f"bench drop-site {self.name} --root-password {mysql_password}"],
		}
		frappe.enqueue(
			"bench_manager.bench_manager.utils.run_command",
			commands=commands[caller],
			doctype=self.doctype,
			timestamp=timestamp,
			docname=self.name,
		)
		return "executed"


@frappe.whitelist()
def get_installable_apps(site_name, doctype, docname):
	verify_whitelisted_call()
	cmd = ["bench", "--site", site_name, "list-apps"]
	result = subprocess.run(cmd, shell=False, capture_output=True, text=True, check=True)
	# frappe    15.77.0 version-15
	# orchestra 0.0.1   develop
	result_list = result.stdout.strip().splitlines()
	installed_apps = (element.split(" ")[0] for element in result_list)
	installable_apps = set(frappe.get_all_apps()) - set(installed_apps)
	return (x for x in installable_apps)


@frappe.whitelist()
def get_removable_apps(doctype, docname):
	verify_whitelisted_call()
	removable_app_list = frappe.get_doc(doctype, docname).app_list.split("\n")
	removable_apps = [app.split(" ")[0] for app in removable_app_list]
	removable_apps.remove("frappe")
	return removable_apps


@frappe.whitelist()
def pass_exists(doctype, docname=""):
	verify_whitelisted_call()
	# return string convention 'TT',<root_password>,<admin_password>
	ret = {"condition": "", "root_password": "", "admin_password": ""}
	common_site_config_path = "common_site_config.json"
	with open(common_site_config_path) as f:
		common_site_config_data = json.load(f)

	ret["condition"] += "T" if common_site_config_data.get("root_password") else "F"
	ret["root_password"] = common_site_config_data.get("root_password")

	ret["condition"] += "T" if common_site_config_data.get("admin_password") else "F"
	ret["admin_password"] = common_site_config_data.get("admin_password")

	if docname == "":  # Prompt reached here on new-site
		return ret

	site_config_path = docname + "/site_config.json"
	with open(site_config_path) as f:
		site_config_data = json.load(f)
	# FF FT TF
	if ret["condition"][1] == "F":
		ret["condition"] = ret["condition"][0] + "T" if site_config_data.get("admin_password") else "F"
		ret["admin_password"] = site_config_data.get("admin_password")
	else:
		if site_config_data.get("admin_password"):
			ret["condition"] = ret["condition"][0] + "T"
			ret["admin_password"] = site_config_data.get("admin_password")
	return ret


@frappe.whitelist()
def verify_password(site_name, mysql_password):
	verify_whitelisted_call()
	try:
		db = pymysql.connect(host=frappe.conf.db_host or "localhost", user="root", passwd=mysql_password)
		db.close()
	except Exception as e:
		print(e)
		frappe.throw("MySQL password is incorrect")
	return "console"


@frappe.whitelist()
def create_site(site_name, install_erpnext, mysql_password, admin_password, timestamp, a_async=True):
	verify_whitelisted_call()
	commands = [
		f"bench new-site {site_name} --mariadb-root-password {mysql_password} --admin-password {admin_password}"
	]
	if install_erpnext == "true":
		with open("apps.txt") as f:
			app_list = f.read()
		if "erpnext" not in app_list:
			commands.append("bench get-app erpnext")
		commands.append(f"bench --site {site_name} install-app erpnext")
		commands.append(f"bench --site {site_name} migrate")

	frappe.enqueue(
		"bench_manager.bench_manager.doctype.site.site.job_site_creation",
		commands=commands,
		doctype="Bench Settings",
		timestamp=timestamp,
		site_name=site_name,
		is_async=a_async,
	)


def job_site_creation(commands, doctype, timestamp, site_name):
	from bench_manager.bench_manager.utils import run_command

	run_command(commands=commands, doctype="Bench Settings", timestamp=timestamp)
	sync_sites()
	site = frappe.get_doc("Site", site_name)
	if site.developer_flag == 1:
		site.update_app_list()
	site.save()
	frappe.db.commit()
