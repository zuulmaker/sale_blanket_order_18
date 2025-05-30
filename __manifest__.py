# Copyright 2018 Acsone
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Sale Blanket Orders",
    "category": "Sale",
    "license": "AGPL-3",
    "author": "Albrecht Zwick GmbH - Johanes Simon Drees / Klaus-Dieter Gundermann",
    "version": "18.0.1.0.0",
    "summary": "Blanket Orders",
    "depends": ["base", "uom", "sale_management", "mail", "analytic"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "data/ir_cron.xml",
        "wizard/create_sale_orders.xml",
        "views/sale_config_settings.xml",
        "views/sale_blanket_order_views.xml",
        "views/sale_blanket_order_line_views.xml",
        "views/sale_order_views.xml",
        "report/templates.xml",
        "report/report.xml",
    ],
    "installable": True,
}
