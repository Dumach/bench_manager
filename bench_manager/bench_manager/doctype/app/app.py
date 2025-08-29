# Copyright (c) 2017, Frappe and contributors
# For license information, please see license.txt


import os
import re
import shlex
import time
import tomllib
from subprocess import PIPE, STDOUT, Popen, check_output

import frappe
from bench_manager.bench_manager.utils import (
	safe_decode,
	verify_whitelisted_call,
)
from frappe.model.document import Document


class App(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		app_color: DF.Data | None
		app_description: DF.Data
		app_email: DF.Data
		app_icon: DF.Data | None
		app_license: DF.Data | None
		app_name: DF.Data
		app_publisher: DF.Data
		app_title: DF.Data | None
		bench_settings: DF.Data | None
		current_git_branch: DF.Data | None
		developer_flag: DF.Int
		is_git_repo: DF.Check
		version: DF.Data | None
	# end: auto-generated types
	app_info_fields = [
		"app_title",
		"app_description",
		"app_publisher",
		"app_email",
		"app_icon",
		"app_color",
		"app_license",
	]

	# def validate(self):
		# if self.get("__islocal"):
		# 	# if self.developer_flag == 0:
		# 	# 	frappe.throw("Creation of new apps is not supported at the moment!")
		# 	self.developer_flag = 0
		# 	self.update_app_details()
		# else:
		# 	if self.developer_flag == 0:
		# 		self.update_app_details()

	def onload(self):
		self.update_app_details()

	def get_attr(self, varname):
		return getattr(self, varname)

	def set_attr(self, varname, varval):
		return setattr(self, varname, varval)

	def after_command(self, commands=None):
		frappe.publish_realtime("Bench-Manager:reload-page")

	def on_trash(self):
		from frappe.utils import now
		try:
			timestamp = now()
			command = ["bench remove-app {app_name}".format(app_name=self.app_name)]
			frappe.enqueue(
				"bench_manager.bench_manager.utils.run_command",
				commands=command,
				cwd=os.path.join("..", "apps", self.name),
				doctype=self.doctype,
				timestamp=timestamp,
				docname=self.name,
			)
		except Exception as e:
			frappe.log_error(frappe.get_traceback(),e)

	@frappe.whitelist()
	def update_app_details(self):
		from frappe.utils.change_log import get_app_branch
		from git import Repo
		from git.exc import InvalidGitRepositoryError

		hooks = frappe.get_hooks(app_name=self.app_name)
		self.app_title = (hooks.get("app_title") or ["App Title"])[0]
		self.app_publisher = (hooks.get("app_publisher") or ["App Publisher"])[0]
		self.app_description = (hooks.get("app_description") or ["App Description"])[0]
		self.app_email = (hooks.get("app_email") or ["App Email"])[0]
		self.app_license = (hooks.get("app_license") or [""])[0]
		self.app_color = (hooks.get("app_color") or [""])[0]
		self.app_icon = (hooks.get("app_icon") or [""])[0]
		# self.developer_flag developer_flag: DF.Int
		self.is_git_repo = True

		module = frappe.get_module(self.app_name)
		self.current_git_branch = get_app_branch(self.app_name)
		self.version = getattr(hooks, f"{self.current_git_branch}_version", None) or module.__version__
		self.save()
		frappe.db.commit()


	@frappe.whitelist()
	def pull_rebase(self, timestamp, remote):
		remote, branch_name = remote.split("/")
		self.console_command(
			timestamp=timestamp, caller="pull-rebase", branch_name=branch_name, remote=remote
		)

	@frappe.whitelist()
	def console_command(self, timestamp, caller, branch_name=None, remote=None, commit_msg=None):
		commands = {
			"git_init": ["git init", "git add .", "git commit -m 'Initial Commit'"],
			"switch_branch": ["git checkout {branch_name}".format(branch_name=branch_name)],
			"new_branch": ["git branch {branch_name}".format(branch_name=branch_name)],
			"delete_branch": ["git branch -D {branch_name}".format(branch_name=branch_name)],
			"git_fetch": ["git fetch --all"],
			"track-remote": [
				"git checkout -b {branch_name} -t {remote}".format(
					branch_name=branch_name, remote=remote
				)
			],
			"pull-rebase": [
				"git pull --rebase {remote} {branch_name}".format(
					branch_name=branch_name, remote=remote
				)
			],
			"commit": [
				"git add .",
				'git commit -m "{commit_msg}"'.format(commit_msg=commit_msg),
			],
			"stash": ["git add .", "git stash"],
			"apply-stash": ["git stash apply"],
		}
		frappe.enqueue(
			"bench_manager.bench_manager.utils.run_command",
			commands=commands[caller],
			cwd=os.path.join("..", "apps", self.name),
			doctype=self.doctype,
			timestamp=timestamp,
			docname=self.name,
		)


@frappe.whitelist()
def get_branches(doctype, docname, current_branch):
	verify_whitelisted_call()
	app_path = os.path.join("..", "apps", docname)  #'../apps/'+docname
	branches = (check_output("git branch".split(), cwd=app_path)).split()
	branches.remove("*")
	branches.remove(current_branch)
	return branches


@frappe.whitelist()
def get_remotes(docname):
	command = "git branch -r"
	remotes = (
		safe_decode(
			check_output(shlex.split(command), cwd=os.path.join("..", "apps", docname))
		)
		.strip("\n")
		.split("\n  ")
	)
	remotes = [remote for remote in remotes if "HEAD" not in remote]
	return remotes
