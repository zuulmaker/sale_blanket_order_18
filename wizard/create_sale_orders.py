# -*- coding: utf-8 -*-
# Copyright 2025 
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Date: 2025-06-02
# Authors: j.s.drees@az-zwick.com 

"""
Sale Blanket Order Wizard - Korrigierte Version für Odoo 18.0
============================================================

Fehlertoleante und robuste Wizard-Implementation für Sale Order Erstellung.

Anwendungsbeispiele:
- Sale Orders aus Blanket Orders erstellen
- Multi-Partner Support
- Mengen-Validierung mit Floating-Point-Toleranz
- Robuste Fehlerbehandlung
- Idempotente Operationen
"""

import logging
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero, float_compare

_logger = logging.getLogger(__name__)


class BlanketOrderWizardLine(models.TransientModel):
    _name = "sale.blanket.order.wizard.line"
    _inherit = "analytic.mixin"
    _description = "Blanket order wizard line"

    wizard_id = fields.Many2one(
        "sale.blanket.order.wizard", 
        ondelete='cascade',
        required=True
    )
    
    blanket_line_id = fields.Many2one(
        "sale.blanket.order.line", 
        ondelete='cascade',
        required=True
    )
    
    analytic_distribution = fields.Json(
        related="blanket_line_id.analytic_distribution",
        readonly=False
    )
    
    product_id = fields.Many2one(
        "product.product", 
        related="blanket_line_id.product_id", 
        string="Product",
        readonly=True
    )
    
    product_uom = fields.Many2one(
        "uom.uom", 
        related="blanket_line_id.product_uom", 
        string="Unit of Measure",
        readonly=True
    )
    
    date_schedule = fields.Date(
        string="Scheduled Date",
        help="Delivery date for this line in the sale order"
    )
    
    remaining_uom_qty = fields.Float(
        related="blanket_line_id.remaining_uom_qty", 
        readonly=True,
        string="Available Qty"
    )
    
    qty = fields.Float(
        string="Quantity to Order", 
        required=True, 
        default=0.0,
        help="Quantity to include in the sale order"
    )
    
    price_unit = fields.Float(
        related="blanket_line_id.price_unit",
        readonly=True
    )
    
    currency_id = fields.Many2one(
        "res.currency", 
        related="blanket_line_id.currency_id",
        readonly=True
    )
    
    partner_id = fields.Many2one(
        "res.partner", 
        related="blanket_line_id.partner_id", 
        string="Customer",
        readonly=True
    )
    
    taxes_id = fields.Many2many(
        "account.tax", 
        related="blanket_line_id.taxes_id", 
        readonly=True
    )

    price_subtotal = fields.Monetary(
        string="Subtotal",
        compute='_compute_price_subtotal',
        store=False,
        currency_field='currency_id'
    )

    @api.depends('qty', 'price_unit')
    def _compute_price_subtotal(self):
        """Berechne Subtotal für Wizard Line"""
        for line in self:
            try:
                line.price_subtotal = line.qty * line.price_unit
            except Exception as e:
                _logger.warning("Fehler bei Subtotal-Berechnung: %s", str(e))
                line.price_subtotal = 0.0

    @api.constrains('qty', 'remaining_uom_qty')
    def _check_qty_limits(self):
        """
        Fehlertoleante Mengen-Validierung
        
        Anwendungsbeispiel:
        - Floating-Point-tolerante Vergleiche
        - Benutzerfreundliche Fehlermeldungen
        - Robuste Edge-Case-Behandlung
        """
        for line in self:
            try:
                if line.qty < 0:
                    raise ValidationError(_("Quantity cannot be negative."))

                precision_digits = 3
                precision = 10 ** -precision_digits

                if float_is_zero(line.remaining_uom_qty, precision_digits=precision_digits):
                    if line.qty > precision:
                        raise ValidationError(
                            _("No remaining quantity available for product %s")
                            % (line.product_id.name or 'Unknown')
                        )
                    continue

                # Prüfe Überschreitung mit Toleranz
                if float_compare(line.qty, line.remaining_uom_qty, precision_digits=precision_digits) > 0:
                    raise ValidationError(
                        _("Quantity to order (%.3f) cannot exceed remaining quantity (%.3f) for product %s")
                        % (line.qty, line.remaining_uom_qty, line.product_id.name or 'Unknown')
                    )

            except ValidationError:
                raise
            except Exception as e:
                _logger.error("Unerwarteter Fehler bei Mengen-Validierung: %s", str(e))
                raise ValidationError(
                    _("Error validating quantities: %s") % str(e)
                )


class BlanketOrderWizard(models.TransientModel):
    _name = "sale.blanket.order.wizard"
    _description = "Create Sale Orders from Blanket Order"

    @api.model
    def _default_order(self):
        """
        Sichere Blanket Order Ermittlung
        
        Anwendungsbeispiel:
        - Context-basierte Order-Detection
        - Automatische Expiration-Prüfung
        - Robuste Error-Handling
        """
        try:
            # Auto-Expiration vor Processing
            self.env["sale.blanket.order"].expire_orders()
            
            active_id = self.env.context.get("active_id")
            if not active_id:
                return False
                
            blanket_order = self.env["sale.blanket.order"].browse(active_id)
            if not blanket_order.exists():
                return False

            # Status-Validierung
            if blanket_order.state == "expired":
                raise UserError(
                    _("Cannot create sale orders from expired blanket order %s!")
                    % blanket_order.name
                )
                
            if blanket_order.state != "open":
                raise UserError(
                    _("Blanket order %s must be in 'Open' state to create sale orders (current: %s)")
                    % (blanket_order.name, blanket_order.state)
                )
                
            return blanket_order
            
        except UserError:
            raise
        except Exception as e:
            _logger.error("Fehler bei _default_order: %s", str(e))
            raise UserError(
                _("Error loading blanket order: %s") % str(e)
            )

    @api.model
    def _check_valid_blanket_order_line(self, bo_lines):
        """
        Umfassende Blanket Order Line Validierung
        
        Anwendungsbeispiel:
        - Multi-Company Konsistenz
        - State-Validierung
        - Verfügbarkeits-Prüfung
        """
        if not bo_lines:
            raise UserError(_("No blanket order lines provided."))

        precision_digits = 3
        company_id = None

        valid_lines = bo_lines.filtered(
            lambda line: not float_is_zero(line.remaining_uom_qty, precision_digits=precision_digits)
        )

        if not valid_lines:
            raise UserError(
                _("All selected lines have already been completely ordered. "
                  "No remaining quantities available.")
            )

        # Line-by-Line Validierung
        for line in bo_lines:
            try:
                if not line.order_id:
                    raise UserError(
                        _("Line %s has no associated blanket order.") % (line.id)
                    )

                if line.order_id.state != "open":
                    raise UserError(
                        _("Blanket Order %s is not open (current state: %s)")
                        % (line.order_id.name, line.order_id.state)
                    )

                line_company_id = line.order_id.company_id.id if line.order_id.company_id else None
                
                if company_id is None:
                    company_id = line_company_id
                elif company_id != line_company_id:
                    raise UserError(
                        _("You have to select lines from the same company. "
                          "Found companies: %s vs %s") 
                        % (company_id, line_company_id)
                    )

            except UserError:
                raise
            except Exception as e:
                _logger.error("Fehler bei Line-Validierung %s: %s", line.id, str(e))
                raise UserError(
                    _("Error validating line %s: %s") % (line.id, str(e))
                )

    @api.model
    def _default_lines(self):
        """
        Intelligente Default Line Generierung
        
        Anwendungsbeispiel:
        - Context-aware Line-Detection
        - Automatische Mengen-Vorschläge
        - Robuste Fallback-Mechanismen
        """
        try:
            blanket_order_line_obj = self.env["sale.blanket.order.line"]
            active_model = self.env.context.get("active_model", False)
            active_ids = self.env.context.get("active_ids", [])

            # Determine Source: Blanket Order oder Blanket Order Lines
            if active_model == "sale.blanket.order":
                blanket_order = self._default_order()
                if not blanket_order:
                    return []
                bo_lines = blanket_order.line_ids
            elif active_model == "sale.blanket.order.line":
                bo_lines = blanket_order_line_obj.browse(active_ids)
            else:
                _logger.warning("Unbekanntes active_model: %s", active_model)
                return []

            if not bo_lines:
                return []

            self._check_valid_blanket_order_line(bo_lines)

            lines = []
            for bol in bo_lines.filtered(
                lambda line: not line.display_type and line.remaining_uom_qty > 0.0
            ):
                try:
                    line_vals = {
                        "blanket_line_id": bol.id,
                        "date_schedule": bol.date_schedule or fields.Date.context_today(self),
                        "qty": bol.remaining_uom_qty,  # Vorschlag: Komplette verfügbare Menge
                    }
                    
                    lines.append(fields.Command.create(line_vals))
                    
                except Exception as e:
                    _logger.warning(
                        "Fehler beim Erstellen der Wizard Line für %s: %s", 
                        bol.id, str(e)
                    )
                    continue

            _logger.info("Generiert %d Wizard Lines", len(lines))
            return lines
            
        except UserError:
            raise
        except Exception as e:
            _logger.error("Fehler bei _default_lines: %s", str(e))
            return []

    # ===================================================================
    # FIELDS
    # ===================================================================

    blanket_order_id = fields.Many2one(
        comodel_name="sale.blanket.order",
        string="Blanket Order",
        readonly=True,
        default=lambda self: self._default_order(),
    )
    
    sale_order_id = fields.Many2one(
        "sale.order", 
        string="Sale Order", 
        domain=[("state", "=", "draft")],
        help="Optional: Add lines to existing draft sale order"
    )
    
    line_ids = fields.One2many(
        "sale.blanket.order.wizard.line",
        "wizard_id",
        string="Order Lines",
        default=_default_lines,
    )

    line_count = fields.Integer(
        string="Line Count",
        compute='_compute_line_summary'
    )
    
    total_amount = fields.Monetary(
        string="Total Amount",
        compute='_compute_line_summary',
        currency_field='currency_id'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        compute='_compute_line_summary'
    )

    @api.depends('line_ids', 'line_ids.qty', 'line_ids.price_unit')
    def _compute_line_summary(self):
        """Berechne Summary-Informationen"""
        for wizard in self:
            try:
                valid_lines = wizard.line_ids.filtered(lambda l: l.qty > 0)
                wizard.line_count = len(valid_lines)
                
                if valid_lines:
                    # Nehme Währung der ersten Linie
                    wizard.currency_id = valid_lines[0].currency_id
                    wizard.total_amount = sum(line.price_subtotal for line in valid_lines)
                else:
                    wizard.currency_id = False
                    wizard.total_amount = 0.0
                    
            except Exception as e:
                _logger.warning("Fehler bei Summary-Berechnung: %s", str(e))
                wizard.line_count = 0
                wizard.total_amount = 0.0
                wizard.currency_id = False

    # ===================================================================
    # BUSINESS METHODS
    # ===================================================================

    def _prepare_so_line_vals(self, line):
        """
        Sale Order Line Values vorbereiten
        
        Anwendungsbeispiel:
        - Robuste Werte-Extraktion
        - Analytic Distribution Mapping
        - Tax-Synchronisation
        - Defensive Programming
        """
        if not line.blanket_line_id:
            raise UserError(_("Wizard line has no associated blanket order line."))

        try:
            blanket_line = line.blanket_line_id
            
            vals = {
                "product_id": blanket_line.product_id.id if blanket_line.product_id else False,
                "name": blanket_line.name or (blanket_line.product_id.name if blanket_line.product_id else _("Unknown Product")),
                "product_uom": blanket_line.product_uom.id if blanket_line.product_uom else False,
                "sequence": getattr(blanket_line, 'sequence', 10),
                "price_unit": blanket_line.price_unit or 0.0,
                "blanket_order_line": blanket_line.id,
                "product_uom_qty": line.qty or 0.0,
            }

            if hasattr(line, 'analytic_distribution') and line.analytic_distribution:
                vals["analytic_distribution"] = line.analytic_distribution

            if blanket_line.taxes_id:
                vals["tax_id"] = [fields.Command.set(blanket_line.taxes_id.ids)]


            if line.date_schedule:
                vals["commitment_date"] = line.date_schedule

            return vals
            
        except Exception as e:
            _logger.error("Fehler bei _prepare_so_line_vals: %s", str(e))
            raise UserError(
                _("Error preparing sale order line values: %s") % str(e)
            )

    def _prepare_so_vals(self, customer_id, global_values):
        """
        Sale Order Values vorbereiten
        
        Anwendungsbeispiel:
        - Customer-spezifische SO-Erstellung
        - Globale Werte-Inheritance
        - Blanket Order Referenz-Mapping
        """
        if not self.blanket_order_id:
            raise UserError(_("No blanket order associated with this wizard."))

        try:
            customer = self.env['res.partner'].browse(customer_id)
            blanket_order = self.blanket_order_id

            vals = {
                "partner_id": customer_id,
                "origin": blanket_order.name,
                "order_line": global_values["order_lines_by_customer"].get(customer_id, []),
            }

            if blanket_order.user_id:
                vals["user_id"] = blanket_order.user_id.id
            if blanket_order.currency_id:
                vals["currency_id"] = blanket_order.currency_id.id
            if blanket_order.pricelist_id:
                vals["pricelist_id"] = blanket_order.pricelist_id.id
            if blanket_order.payment_term_id:
                vals["payment_term_id"] = blanket_order.payment_term_id.id
            if blanket_order.team_id:
                vals["team_id"] = blanket_order.team_id.id
            if blanket_order.company_id:
                vals["company_id"] = blanket_order.company_id.id

            if hasattr(blanket_order, 'analytic_distribution') and blanket_order.analytic_distribution:
                vals["analytic_distribution"] = blanket_order.analytic_distribution

            try:
                addr = customer.address_get(['delivery', 'invoice'])
                vals.update({
                    "partner_invoice_id": addr.get('invoice', customer_id),
                    "partner_shipping_id": addr.get('delivery', customer_id),
                })
            except Exception as addr_error:
                _logger.warning("Fehler bei Adress-Ermittlung: %s", str(addr_error))

            return vals
            
        except Exception as e:
            _logger.error("Fehler bei _prepare_so_vals: %s", str(e))
            raise UserError(
                _("Error preparing sale order values: %s") % str(e)
            )

    def create_sale_order(self):
        """
        Haupt-Methode für Sale Order Erstellung
        
        Anwendungsbeispiel:
        - Multi-Customer Support
        - Robuste Error-Handling
        - Transactional Safety
        - User Feedback
        """
        if not self.line_ids:
            raise UserError(_("No lines selected for order creation."))

        # Nur Linien mit Menge > 0 verarbeiten
        valid_lines = self.line_ids.filtered(lambda line: line.qty > 0.0)
        if not valid_lines:
            raise UserError(_("No lines with quantity > 0 selected."))

        try:
            # Nach Customer gruppieren
            order_lines_by_customer = defaultdict(list)
            currencies = set()
            
            for line in valid_lines:
                # Mengen-Validierung
                if line.qty > line.remaining_uom_qty:
                    raise UserError(
                        _("Cannot order %.3f of %s - only %.3f remaining") 
                        % (line.qty, line.product_id.name, line.remaining_uom_qty)
                    )

                # Sale Order Line vorbereiten
                line_vals = self._prepare_so_line_vals(line)
                customer_id = line.partner_id.id if line.partner_id else False
                
                if not customer_id:
                    raise UserError(_("Line has no associated customer."))

                order_lines_by_customer[customer_id].append((0, 0, line_vals))
                
                # Währungs-Konsistenz tracken
                if line.currency_id:
                    currencies.add(line.currency_id.id)

            if not order_lines_by_customer:
                raise UserError(_("No valid order lines to create."))

            # Multi-Currency Validation
            if len(currencies) > 1:
                raise UserError(
                    _("Cannot create sale orders from blanket order lines with different currencies")
                )

            # Sale Orders erstellen
            created_orders = []
            global_values = {"order_lines_by_customer": order_lines_by_customer}
            
            for customer_id in order_lines_by_customer:
                try:
                    order_vals = self._prepare_so_vals(customer_id, global_values)
                    sale_order = self.env["sale.order"].create(order_vals)
                    created_orders.append(sale_order.id)
                    
                    _logger.info(
                        "Sale Order %s erstellt für Customer %s (Zeilen: %d)", 
                        sale_order.name, customer_id, len(order_lines_by_customer[customer_id])
                    )
                    
                except Exception as so_error:
                    _logger.error("Fehler bei SO-Erstellung für Customer %s: %s", customer_id, str(so_error))
                    raise UserError(
                        _("Error creating sale order for customer %s: %s") 
                        % (customer_id, str(so_error))
                    )

            if not created_orders:
                raise UserError(_("No sale orders could be created."))

            # Success Feedback
            success_message = _("Successfully created %d sale order(s)") % len(created_orders)
            _logger.info(success_message)

            # Return Action
            if len(created_orders) == 1:
                # Einzelne SO öffnen
                return {
                    "type": "ir.actions.act_window",
                    "name": _("Created Sale Order"),
                    "view_mode": "form",
                    "res_model": "sale.order",
                    "res_id": created_orders[0],
                    "target": "current",
                }
            else:
                # Liste aller SOs
                return {
                    "type": "ir.actions.act_window",
                    "name": _("Created Sale Orders (%d)") % len(created_orders),
                    "view_mode": "tree,form",
                    "res_model": "sale.order",
                    "domain": [("id", "in", created_orders)],
                    "context": {"from_blanket_order_wizard": True},
                    "target": "current",
                }

        except UserError:
            raise
        except Exception as e:
            _logger.error("Unerwarteter Fehler bei create_sale_order: %s", str(e))
            raise UserError(
                _("Unexpected error creating sale orders: %s") % str(e)
            )
