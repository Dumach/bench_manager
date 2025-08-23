# Copyright (c) 2017, Frappe and contributors
# For license information, please see license.txt

# TODO: bench manager command should not use `timestamp` as a unique identifier
# insted: COMM-sync_apps-20251022.100913

from subprocess import PIPE, Popen, check_output

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname


class BenchManagerCommand(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		bench_settings: DF.Data | None
		command: DF.Text
		console: DF.Code | None
		source: DF.Data
		status: DF.Literal["Success", "Failed", "Ongoing"]
		time_taken: DF.Data | None
		timestamp: DF.Data | None
	# end: auto-generated types
	pass
