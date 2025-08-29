# Copyright (c) 2017, Frappe and contributors
# For license information, please see license.txt


import os
import shlex
from subprocess import check_output

import frappe
from frappe.model.document import Document

from bench_manager.bench_manager.utils import verify_whitelisted_call


class SiteBackup(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		bench_settings: DF.Data | None
		date: DF.Data
		developer_flag: DF.Int
		file_path: DF.Data | None
		hash: DF.Data | None
		private_file_backup: DF.Check
		public_file_backup: DF.Check
		site_name: DF.Data
		stored_location: DF.Data
		time: DF.Data

	# end: auto-generated types
	def autoname(self):
		if self.site_name is None:
			return
		self.name = self.date + " " + self.time + " " + self.site_name + " " + self.stored_location

	def validate(self):
		if self.get("__islocal"):
			if self.developer_flag == 0:
				frappe.throw("If you want to create a backup, then goto Sites")
			self.developer_flag = 0

	def on_trash(self):
		if self.developer_flag == 0:
			base_path = os.path.join("..", self.file_path)

			# Remove database backup file
			db_file = f"{base_path}-database.sql"
			if os.path.isfile(db_file):
				os.remove(db_file)
			else:
				db_file_gz = f"{base_path}-database.sql.gz"
				if os.path.isfile(db_file_gz):
					os.remove(db_file_gz)

			# Remove public files backup
			if self.public_file_backup:
				public_files = f"{base_path}-files.tar"
				if os.path.isfile(public_files):
					os.remove(public_files)

			# Remove private files backup
			if self.private_file_backup:
				private_files = f"{base_path}-private-files.tar"
				if os.path.isfile(private_files):
					os.remove(private_files)

			# Remove site-config
			config_file = f"{base_path}-site_config_backup.json"
			if os.path.isfile(config_file):
				os.remove(config_file)


@frappe.whitelist()
def get_restore_options(doctype, docname):
	verify_whitelisted_call()
	return [x["name"] for x in frappe.get_all("Site")]


@frappe.whitelist()
def restore_backup(
	doctype,
	docname,
	on_a_new_site,
	existing_site,
	new_site_name,
	mysql_password,
	admin_password,
	timestamp,
):
	verify_whitelisted_call()
	backup = frappe.get_doc("Site Backup", docname)
	commands = []
	password_suffix = f"--admin-password {admin_password} --mariadb-root-password {mysql_password}"
	site_name = existing_site
	if on_a_new_site == "1":
		site_name = new_site_name
		commands.append(f"bench new-site {site_name} {password_suffix}")
	command = f"bench --site {site_name} --force restore {backup.file_path}-database.sql"
	if not os.path.isfile(f"{backup.file_path}_database.sql"):
		command += ".gz"
	if backup.public_file_backup:
		command += f" --with-public-files ../{backup.file_path}_files.tar"
	if backup.private_file_backup:
		command += f" --with-private-files ../{backup.file_path}_private_files.tar"
	command += f" {password_suffix}"
	commands.append(command)
	frappe.enqueue(
		"bench_manager.bench_manager.utils.run_command",
		commands=commands,
		doctype=doctype,
		timestamp=timestamp,
		docname=docname,
	)
