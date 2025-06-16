# -*- coding: utf-8 -*-
"""
# Copyright 2025 j.s.drees@az-zwick.com & kd.gundermann@az-zwick.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

Sale Blanket Order Line - Standalone Model für Odoo 18.0
========================================================
"""
import logging
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError, tax_error
from odoo.tools import float_is_zero, float_compare, formatLang

_logger = logging.getLogger(__name__)


class SaleBlanketOrderLine(models.Model):
    _name = "sale.blanket.order.line"
    _inherit = ["analytic.mixin"]
    _description = "Sale Blanket Order Line"
    _order = "order_id, sequence, id"
    _check_company_auto = True

    # ===================================================================
    # BASIC FIELDS
    # ===================================================================

    order_id = fields.Many2one(
        'sale.blanket.order',
        string='Blanket Order Reference',
        required=True,
        ondelete='cascade',
        index=True,
        copy=False
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Gives the sequence of this line when displaying the blanket order."
    )

    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")
    ], default=False, help="Technical field for UX purpose.")

    # Product Information
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        domain="[('sale_ok', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        change_default=True,
        ondelete='restrict',
        check_company=True
    )

    name = fields.Text(
        string='Description',
        required=True
    )

    # Quantities
    product_uom_qty = fields.Float(
        string='Quantity',
        digits='Product Unit of Measure',
        required=True,
        default=1.0
    )

    product_uom = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        domain="[('category_id', '=', product_uom_category_id)]"
    )

    product_uom_category_id = fields.Many2one(
        related='product_id.uom_id.category_id',
        readonly=True
    )

    # Dates
    date_schedule = fields.Date(
        string='Scheduled Date',
        help="Expected delivery date for this line."
    )

    # Pricing
    price_unit = fields.Float(
        'Unit Price',
        required=True,
        digits='Product Price',
        default=0.0
    )

    taxes_id = fields.Many2many(
        'account.tax',
        string='Taxes',
        domain="[('type_tax_use', '=', 'sale'), ('company_id', '=', company_id)]",
        check_company=True
    )

    # Computed amounts
    price_subtotal = fields.Monetary(
        compute='_compute_amount',
        string='Subtotal',
        readonly=True,
        store=True
    )

    price_tax = fields.Float(
        compute='_compute_amount',
        string='Total Tax',
        readonly=True,
        store=True
    )

    price_total = fields.Monetary(
        compute='_compute_amount',
        string='Total',
        readonly=True,
        store=True
    )

    # Remaining quantities
    ordered_uom_qty = fields.Float(
        string='Ordered Quantity',
        compute='_compute_ordered_qty',
        store=True,
        help="Quantity already ordered in sale orders."
    )

    remaining_uom_qty = fields.Float(
        string='Remaining Quantity',
        compute='_compute_remaining_qty',
        store=True,
        help="Quantity remaining to be ordered."
    )

    remaining_qty_percent = fields.Float(
        string='Remaining %',
        compute='_compute_remaining_qty',
        store=True
    )

    # Relations
    company_id = fields.Many2one(
        related='order_id.company_id',
        string='Company',
        store=True,
        readonly=True,
        index=True
    )

    partner_id = fields.Many2one(
        related='order_id.partner_id',
        string='Customer',
        readonly=True,
        store=True
    )

    currency_id = fields.Many2one(
        related='order_id.currency_id',
        depends=['order_id.currency_id'],
        store=True,
        readonly=True
    )

    state = fields.Selection(
        related='order_id.state',
        string='Blanket Order Status',
        readonly=True,
        copy=False,
        store=True
    )

    # ===================================================================
    # COMPUTE METHODS
    # ===================================================================

    @api.depends('product_uom_qty', 'price_unit', 'taxes_id')
    def _compute_amount(self):
        """
        Fehlertoleante Preis-Berechnung

        Anwendungsbeispiel:
        - Robuste Steuer-Berechnung
        - Währungs-Handling
        - UoM-Konvertierung
        """
        for line in self:
            try:
                # Display Type Lines haben keine Preise
                if line.display_type:
                    line.update({
                        'price_subtotal': 0.0,
                        'price_tax': 0.0,
                        'price_total': 0.0,
                    })
                    continue

                # Basis-Berechnung
                price = line.price_unit * (1 - 0.0 / 100.0)  # TODO: Discount hinzufügen
                quantity = line.product_uom_qty or 0.0

                # Steuer-Berechnung
                if line.taxes_id and line.order_id.currency_id:
                    try:

                        taxes = line.taxes_id.compute_all(
                            price,
                            line.order_id.currency_id,
                            quantity,
                            product=line.product_id,
                            partner=line.order_id.partner_shipping_id
                        )

                        line.update({
                            'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                            'price_total': taxes.get('total_included', 0.0),
                            'price_subtotal': taxes.get('total_excluded', 0.0),
                        })
                    else:
                        subtotal = price * quantity
                        line.update({
                            'price_tax': 0.0,
                            'price_total': subtotal,
                            'price_subtotal': subtotal,
                        })
                    except Exception as tax_error:
                        _logger.warning("Steuerberechnung fehlgeschlagen: %s", tax_error)
                        # Fallback ohne Steuern
                        subtotal = price * quantity
                        line.update({
                            'price_tax': 0.0,
                            'price_total': subtotal,
                            'price_subtotal': subtotal,
                        })

            except Exception as e:
                _logger.error(
                    "Fehler bei _compute_amount für Line %s: %s",
                    line.id, str(e)
                )
                line.update({
                    'price_subtotal': 0.0,
                    'price_tax': 0.0,
                    'price_total': 0.0,
                })

    @api.depends('product_uom_qty')
    def _compute_ordered_qty(self):
        """
        Berechnung bereits bestellter Mengen

        Anwendungsbeispiel:
        - Tracking von Sale Order Lines
        - Robuste Mengen-Aggregation
        - UoM-Konvertierung
        """
        for line in self:
            try:
                if line.display_type:
                    line.ordered_uom_qty = 0.0
                    continue

                # Suche Sale Order Lines die von dieser Blanket Line erstellt wurden
                sale_lines = self.env['sale.order.line'].search([
                    ('blanket_order_line', '=', line.id),
                    ('order_id.state', '!=', 'cancel')
                ])

                total_qty = 0.0
                for sale_line in sale_lines:
                    try:
                        # UoM-Konvertierung falls nötig
                        if sale_line.product_uom != line.product_uom:
                            qty = sale_line.product_uom._compute_quantity(
                                sale_line.product_uom_qty,
                                line.product_uom
                            )
                        else:
                            qty = sale_line.product_uom_qty

                        total_qty += qty

                    except Exception as uom_error:
                        _logger.warning(
                            "UoM Konvertierungs-Fehler für Sale Line %s: %s",
                            sale_line.id, str(uom_error)
                        )
                        total_qty += sale_line.product_uom_qty  # Fallback

                line.ordered_uom_qty = total_qty

            except Exception as e:
                _logger.error(
                    "Fehler bei _compute_ordered_qty für Line %s: %s",
                    line.id, str(e)
                )
                line.ordered_uom_qty = 0.0

    @api.depends('product_uom_qty', 'ordered_uom_qty')
    def _compute_remaining_qty(self):
        """Berechnung verbleibender Mengen"""
        for line in self:
            try:
                if line.display_type:
                    line.remaining_uom_qty = 0.0
                    line.remaining_qty_percent = 0.0
                    continue

                remaining = max(0.0, line.product_uom_qty - line.ordered_uom_qty)
                line.remaining_uom_qty = remaining

                # Prozent berechnen
                if not float_is_zero(line.product_uom_qty, precision_digits=2):
                    percentage = (remaining / line.product_uom_qty) * 100
                    line.remaining_qty_percent = percentage
                else:
                    line.remaining_qty_percent = 0.0

            except Exception as e:
                _logger.error(
                    "Fehler bei _compute_remaining_qty für Line %s: %s",
                    line.id, str(e)
                )
                line.remaining_uom_qty = 0.0
                line.remaining_qty_percent = 0.0

    # ===================================================================
    # ONCHANGE METHODS
    # ===================================================================

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """
        Product-Änderung Handler

        Anwendungsbeispiel:
        - Automatische Beschreibung
        - Preis aus Pricelist
        - UoM-Anpassung
        - Steuer-Update
        """
        if not self.product_id:
            return

        try:
            # Produkt-Beschreibung
            lang = self.env.context.get('lang')
            product = self.product_id.with_context(lang=lang)

            name = product.display_name
            if product.description_sale:
                name += '\n' + product.description_sale

            self.name = name

            # UoM aktualisieren
            if product.uom_id:
                self.product_uom = product.uom_id.id

            # Preis aus Pricelist
            if self.order_id.pricelist_id and self.order_id.partner_id:
                price = self.order_id.pricelist_id._get_product_price(
                    product,
                    self.product_uom_qty or 1.0,
                    self.order_id.partner_id,
                    date=self.order_id.date_order,
                    uom_id=self.product_uom.id
                )
                self.price_unit = price

            # Steuern aktualisieren
            fpos = self.order_id.partner_id.property_account_position_id
            if fpos:
                # Steuerposition anwenden
                taxes = product.taxes_id._filter_taxes_by_company(self.company_id)
                self.taxes_id = fpos.map_tax(taxes)
            else:
                self.taxes_id = product.taxes_id._filter_taxes_by_company(self.company_id)

        except Exception as e:
            _logger.warning(
                "Fehler bei _onchange_product_id: %s", str(e)
            )

    @api.onchange('product_uom', 'product_uom_qty')
    def _onchange_product_uom(self):
        """UoM-Änderung Handler"""
        if not self.product_id or not self.product_uom:
            return

        try:
            # Preis entsprechend UoM anpassen
            if self.order_id.pricelist_id:
                price = self.order_id.pricelist_id._get_product_price(
                    self.product_id,
                    self.product_uom_qty or 1.0,
                    self.order_id.partner_id,
                    date=self.order_id.date_order,
                    uom_id=self.product_uom.id
                )
                self.price_unit = price

        except Exception as e:
            _logger.warning(
                "Fehler bei _onchange_product_uom: %s", str(e)
            )

    # ===================================================================
    # CONSTRAINTS
    # ===================================================================

    @api.constrains('product_uom_qty')
    def _check_product_uom_qty(self):
        """Validierung Produktmenge"""
        for line in self:
            if not line.display_type and line.product_uom_qty <= 0:
                raise ValidationError(
                    _("Quantity must be positive for product lines!")
                )

    @api.constrains('price_unit')
    def _check_price_unit(self):
        """Validierung Einzelpreis"""
        for line in self:
            if not line.display_type and line.price_unit < 0:
                raise ValidationError(
                    _("Unit price cannot be negative!")
                )

    @api.constrains('product_id', 'product_uom')
    def _check_product_uom_category(self):
        """Validierung UoM-Kategorie"""
        for line in self:
            if line.product_id and line.product_uom:
                if line.product_uom.category_id != line.product_id.uom_id.category_id:
                    raise ValidationError(
                        _("The unit of measure must be in the same category as the product unit of measure!")
                    )

    # ===================================================================
    # BUSINESS METHODS
    # ===================================================================

    def action_view_sale_order_lines(self):
        """Action für verknüpfte Sale Order Lines"""
        try:
            sale_lines = self.env['sale.order.line'].search([
                ('blanket_order_line', '=', self.id)
            ])

            return {
                'type': 'ir.actions.act_window',
                'name': _('Sale Order Lines'),
                'view_mode': 'tree,form',
                'res_model': 'sale.order.line',
                'domain': [('id', 'in', sale_lines.ids)],
                'context': {
                    'search_default_blanket_order_line': self.id,
                }
            }

        except Exception as e:
            _logger.error("Fehler bei action_view_sale_order_lines: %s", str(e))
            raise UserError(_("Error viewing sale order lines: %s") % str(e))

    def name_get(self):
        """Erweiterte Anzeige"""
        result = []
        for line in self:
            try:
                if line.display_type:
                    name = line.name
                else:
                    name = f"[{line.product_id.default_code or ''}] {line.name or ''}"
                    if line.product_uom_qty:
                        name = f"{name} ({formatLang(self.env, line.product_uom_qty)} {line.product_uom.name})"

                result.append((line.id, name))

            except Exception as e:
                _logger.warning("Fehler bei name_get: %s", str(e))
                result.append((line.id, line.name or 'Draft Line'))

        return result

    @api.model
    def create(self, vals):
        """Fehlertoleante Erstellung"""
        try:
            # Sequenz auto-generieren falls nicht gesetzt
            if 'sequence' not in vals and 'order_id' in vals:
                order = self.env['sale.blanket.order'].browse(vals['order_id'])
                max_sequence = max(order.line_ids.mapped('sequence') or [0])
                vals['sequence'] = max_sequence + 10

            return super().create(vals)

        except Exception as e:
            _logger.error("Fehler bei Line-Erstellung: %s", str(e))
            raise

    def write(self, vals):
        """Fehlertoleante Aktualisierung"""
        try:
            return super().write(vals)
        except Exception as e:
            _logger.error("Fehler bei Line-Update: %s", str(e))
            raise