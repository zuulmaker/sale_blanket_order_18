# -*- coding: utf-8 -*-
# Copyright 2025 Albrecht Zwick GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Date: 2025-06-02
# Author: j.s.drees@az-zwick.com
{
    "name": "Zwick | Sale Blanket Orders",
    "category": "Sales",
    "license": "AGPL-3",
    "author": "Albrecht Zwick GmbH - Johanes Simon Drees",
    "version": "18.0.1.0.0",
    "development_status": "Alpha",
    "summary": "Enables Blanket Orders on Sales",
    "depends": ["base", "mail", "sale", "sale_management", "analytic", "uom", 'product', 'account', 'stock' ],
    "data": [
        "security/sale_blanket_order_security.xml",
        "security/ir.model.access.csv",
        "data/sequence_data.xml",
        "data/ir_cron.xml",
        "views/sale_blanket_order_views.xml",
        "views/sale_blanket_order_line_views.xml",
        "views/sale_order_views.xml",
        "wizard/create_sale_orders.xml",
        "views/wizard_views.xml",
        "views/sale_blanket_order_menu.xml",
        "report/sale_blanket_order_templates.xml",
        "report/sale_blanket_order_report.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": True,
    "sequence": 100,
    "external_dependencies": {
        'python': ['dateutil'],
    },

    "odoo_version": '>=18.0'
}




