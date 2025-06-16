# -*- coding: utf-8 -*-
# Copyright 2025 j.s.drees@az-zwick.com & kd.gundermann@az-zwick.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Date: 2025-06-02
# Authors: J.s.drees@az-zwick.com & kd.gundermann@az-zwick.com
from collections import defaultdict
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)

class BlanketOrderWizardLine(models.TransientModel):
    _name = "sale.blanket.order.wizard.line"
    _inherit = "analytic.mixin"
    _description = "Blanket order wizard line"

    wizard_id = fields.Many2one("sale.blanket.order.wizard",ondelete='cascade')
    blanket_line_id = fields.Many2one("sale.blanket.order.line",ondelete='cascade')
    analytic_distribution = fields.Json(related="blanket_line_id.analytic_distribution")
    product_id = fields.Many2one(
        "product.product", related="blanket_line_id.product_id", string="Product"
    )
    product_uom = fields.Many2one(
        "uom.uom", related="blanket_line_id.product_uom", string="Unit of Measure"
    )
    date_schedule = fields.Date(string="Scheduled Date")
    remaining_uom_qty = fields.Float(related="blanket_line_id.remaining_uom_qty", readonly=True)
    qty = fields.Float(string="Quantity to Order", required=True, default=0.0)
    price_unit = fields.Float(related="blanket_line_id.price_unit")
    currency_id = fields.Many2one("res.currency", related="blanket_line_id.currency_id")
    partner_id = fields.Many2one(
        "res.partner", related="blanket_line_id.partner_id", string="Customer"
    )
    taxes_id = fields.Many2many("account.tax", related="blanket_line_id.taxes_id", readonly=True)


    @api.constrains('qty', 'remaining_uom_qty')
    def _check_qty_limits(self):
        """Fehlertolerant: Validierung der Mengen"""
        for line in self:
            if line.qty < 0:
                raise ValidationError(_("Quantity cannot be negative."))

            # Defensive Prüfung mit Rundung für Floating-Point-Fehler
            precision_digits = 3

            if float_is_zero(line.remaining_uom_qty, precision_digits=precision_digits):
                continue

            if line.qty > line.remaining_uom_qty + (10 ** -precision_digits):
                raise ValidationError(
                    _("Quantity to order (%.2f) cannot exceed remaining quantity (%.2f) for product %s")
                    % (line.qty, line.remaining_uom_qty, line.product_id.name or 'Unknown')
                )


class BlanketOrderWizard(models.TransientModel):
    _name = "sale.blanket.order.wizard"
    _description = "Create Sale Orders from Blanket Order"

    @api.model
    def _default_order(self):
        # in case the cron hasn't run
        self.env["sale.blanket.order"].expire_orders()
        active_id = self.env.context.get("active_id")
        if not active_id:
            return False
        try:
            blanket_order = self.env["sale.blanket.order"].browse(active_id)
            if not blanket_order.exists():
                return False

            if blanket_order.state == "expired":
                raise UserError(
                    _("You can't create a sale order from an expired blanket order!")
                )
            return blanket_order
        except Exception as e:
            raise UserError(
                _("You can't create a sale order from " " an expired blanket order!")
                )


    @api.model
    def _check_valid_blanket_order_line(self, bo_lines):
        if not bo_lines:
            raise UserError(_("No blanket order lines provided."))

        precision_digits = 3  # Standard für Product Unit of Measure
        company_id = False

        # Prüfe ob alle Zeilen bereits vollständig abgearbeitet sind
        valid_lines = bo_lines.filtered(
            lambda line: not float_is_zero(line.remaining_uom_qty, precision_digits=precision_digits)
        )

        if not valid_lines:
            raise UserError(_("All selected lines have already been completely ordered."))

        for line in bo_lines:
            # Defensive Prüfung des Blanket Order Status
            if not line.order_id:
                raise UserError(_("Line has no associated blanket order."))

            if line.order_id.state != "open":
                raise UserError(
                    _("Sale Blanket Order %s is not open (current state: %s)")
                    % (line.order_id.name, line.order_id.state)
                )

            # Company-Konsistenz prüfen
            line_company_id = line.company_id.id if line.company_id else False
            if company_id is not False and line_company_id != company_id:
                raise UserError(_("You have to select lines from the same company."))
            else:
                company_id = line_company_id

    @api.model
    def _default_lines(self):
        try:
            blanket_order_line_obj = self.env["sale.blanket.order.line"]
            blanket_order_line_ids = self.env.context.get("active_ids", [])
            active_model = self.env.context.get("active_model", False)

            if active_model == "sale.blanket.order":
                blanket_order = self._default_order()
                if not blanket_order:
                    return []
                bo_lines = blanket_order.line_ids
            else:
                bo_lines = blanket_order_line_obj.browse(blanket_order_line_ids)

            if not bo_lines:
                return []

            self._check_valid_blanket_order_line(bo_lines)

            lines = []
            for bol in bo_lines.filtered(
                    lambda bo_line: not bo_line.display_type and bo_line.remaining_uom_qty != 0.0
            ):
                try:
                    lines.append(fields.Command.create({
                        "blanket_line_id": bol.id,
                        "date_schedule": bol.date_schedule or fields.Date.context_today(self),
                        "qty": bol.remaining_uom_qty,
                    }))
                except Exception as e:
                    _logger.warning("Could not create wizard line for %s: %s", bol.id, str(e))
                    continue

            return lines
        except Exception as e:
            _logger.error("Error creating default lines: %s", str(e))
            return []

    blanket_order_id = fields.Many2one(
        comodel_name="sale.blanket.order",
        string="Blanket Order",
        readonly=True,
        default=lambda self: self._default_order(),
    )
    sale_order_id = fields.Many2one(
        "sale.order", string="Sale Order", domain=[("state", "=", "draft")]
    )
    line_ids = fields.One2many(
        "sale.blanket.order.wizard.line",
        "wizard_id",
        string="Order Lines",
        default=_default_lines,
    )

    def _prepare_so_line_vals(self, line):
        if not line.blanket_line_id:
            raise UserError(_("Wizard line has no associated blanket order line."))

        blanket_line = line.blanket_line_id
        # Defensive Werte-Extraktion
        vals = {
            "product_id": blanket_line.product_id.id if blanket_line.product_id else False,
            "name": blanket_line.product_id.name or blanket_line.name or _("Unknown Product"),
            "product_uom": blanket_line.product_uom.id if blanket_line.product_uom else False,
            "sequence": getattr(blanket_line, 'sequence', 10),
            "price_unit": blanket_line.price_unit or 0.0,
            "blanket_order_line": blanket_line.id,
            "product_uom_qty": line.qty or 0.0,
        }

        # Optionale Felder defensive hinzufügen
        if hasattr(line, 'analytic_distribution') and line.analytic_distribution:
            vals["analytic_distribution"] = line.analytic_distribution

        if blanket_line.taxes_id:
            vals["tax_id"] = [fields.Command.set(blanket_line.taxes_id.ids)]

        return vals

    def _prepare_so_vals(
        self,
        customer,
        user_id,
        currency_id,
        pricelist_id,
        payment_term_id,
        order_lines_by_customer,
    ):
        if not self.blanket_order_id:
            raise UserError(_("No blanket order associated with this wizard."))

        vals = {
            "partner_id": customer,
            "origin": self.blanket_order_id.name or "",
            "order_line": order_lines_by_customer.get(customer, []),
        }

        # Optionale Felder nur setzen wenn verfügbar
        if user_id:
            vals["user_id"] = user_id
        if currency_id:
            vals["currency_id"] = currency_id
        if pricelist_id:
            vals["pricelist_id"] = pricelist_id
        if payment_term_id:
            vals["payment_term_id"] = payment_term_id
        if self.blanket_order_id.analytic_account_id:
            vals["analytic_account_id"] = self.blanket_order_id.analytic_account_id.id

        return vals

    def create_sale_order(self):
        if not self.line_ids:
            raise UserError(_("No lines selected for order creation."))

        order_lines_by_customer = defaultdict(list)
        currency_id = 0
        pricelist_id = 0
        user_id = 0
        payment_term_id = 0

        for line in self.line_ids.filtered(lambda line: line.qty != 0.0):
            if line.qty > line.remaining_uom_qty:
                raise UserError(_("You can't order more than the remaining quantities"))
            # Sales Order Line vorbereiten
            vals = self._prepare_so_line_vals(line)
            customer_id = line.partner_id.id if line.partner_id else False
            if not customer_id:
                raise UserError(_("Line has no associated customer."))

            order_lines_by_customer[customer_id].append((0, 0, vals))
            # Konsistenz-Checks für globale Werte
            blanket_line = line.blanket_line_id

            if currency_id == 0:
                currency_id = line.blanket_line_id.order_id.currency_id.id
            elif currency_id != line.blanket_line_id.order_id.currency_id.id:
                currency_id = False

            line_pricelist = blanket_line.pricelist_id.id if hasattr(blanket_line,
                                                                     'pricelist_id') and blanket_line.pricelist_id else False
            if pricelist_id is False:
                pricelist_id = line_pricelist
            elif pricelist_id != line_pricelist and line_pricelist:
                pricelist_id = None

            line_user = blanket_line.user_id.id if hasattr(blanket_line, 'user_id') and blanket_line.user_id else False
            if user_id is False:
                user_id = line_user
            elif user_id != line_user and line_user:
                user_id = None

            line_payment_term = blanket_line.payment_term_id.id if hasattr(blanket_line,
                                                                           'payment_term_id') and blanket_line.payment_term_id else False
            if payment_term_id is False:
                payment_term_id = line_payment_term
            elif payment_term_id != line_payment_term and line_payment_term:
                payment_term_id = None

        if not order_lines_by_customer:
            raise UserError(_("An order can't be empty"))

        if not currency_id:
            raise UserError(
                _(
                    "Can not create Sale Order from Blanket "
                    "Order lines with different currencies"
                )
            )
        # Sale order erstellen
        created_orders = []
        try:
            for customer_id in order_lines_by_customer:
                order_vals = self._prepare_so_vals(
                    customer_id, user_id, currency_id, pricelist_id,
                    payment_term_id, order_lines_by_customer
                )

                sale_order = self.env["sale.order"].create(order_vals)
                created_orders.append(sale_order.id)
                #_logger.info("Created sale order %s for customer %s", sale_order.name, customer_id)

        except Exception as e:
            #_logger.error("Error creating sale orders: %s", str(e))
            raise UserError(_("Error creating sale orders: %s") % str(e))

        if not created_orders:
            raise UserError(_("No sale orders could be created."))

            # Return Action
        return {
            "domain": [("id", "in", created_orders)],
            "name": _("Created Sales Orders"),
            "view_type": "form",
            "view_mode": "tree,form",
            "res_model": "sale.order",
            "context": {"from_sale_order": True},
            "type": "ir.actions.act_window",
        }

