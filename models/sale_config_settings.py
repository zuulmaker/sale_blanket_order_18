# -*- coding: utf-8 -*-
# Copyright 2025 j.s.drees@az-zwick.com & kd.gundermann@az-zwick.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Date: 2025-06-02
# Authors: J.s.drees@az-zwick.com & kd.gundermann@az-zwick.com



from odoo import fields, models


class SaleConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    group_blanket_disable_adding_lines = fields.Boolean(
        string="Disable adding more lines to SOs",
        implied_group="sale_blanket_order.blanket_orders_disable_adding_lines",
    )
