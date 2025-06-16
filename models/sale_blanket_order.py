# Copyright 2018 ACSONE SA/NV
# Copyright 2025 Albrecht Zwick GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from datetime import datetime, timedelta
from collections import defaultdict

from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo.tools import float_is_zero, float_compare, format_date
from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)


class SaleBlanketOrder(models.Model):
    _name = "sale.blanket.order"
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]
    _description = "Sale Blanket Order"
    _order = "date_order desc, name desc, id desc"
    _check_company_auto = True
    _rec_name = 'name'

    name = fields.Char(
        string="Order Reference",
        required=True,
        copy=False,
        readonly=True,
        states={'draft': [('readonly', False)]},
        index=True,
        default=lambda self: _('New'),
        tracking=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('expired', 'Expired'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True,
        tracking=True, default='draft')

    # Partner Information
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        change_default=True,
        index=True,
        tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]"
    )

    partner_invoice_id = fields.Many2one(
        'res.partner',
        string='Invoice Address',
        readonly=True,
        states={'draft': [('readonly', False)]},
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]"
    )

    partner_shipping_id = fields.Many2one(
        'res.partner',
        string='Delivery Address',
        readonly=True,
        states={'draft': [('readonly', False)]},
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]"
    )

    # Dates
    date_order = fields.Datetime(
        string='Order Date',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        index=True,
        copy=False,
        default=fields.Datetime.now,
        help="Date when the blanket order was created."
    )

    validity_date = fields.Date(
        string="Validity Date",
        readonly=True,
        states={'draft': [('readonly', False)]},
        copy=False,
        help="Date until which the blanket order is valid."
    )

    # Commercial Information
    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Pricelist',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Pricelist for current blanket order."
    )

    currency_id = fields.Many2one(
        related='pricelist_id.currency_id',
        depends=['pricelist_id'],
        store=True,
        readonly=True
    )

    payment_term_id = fields.Many2one(
        'account.payment.term',
        string='Payment Terms',
        readonly=True,
        states={'draft': [('readonly', False)]},
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]"
    )

    # Lines
    line_ids = fields.One2many(
        'sale.blanket.order.line',
        'order_id',
        string='Order Lines',
        readonly=True,
        states={'draft': [('readonly', False)]},
        copy=True,
        auto_join=True
    )

    # Company and User
    company_id = fields.Many2one(
        'res.company',
        'Company',
        required=True,
        index=True,
        default=lambda self: self.env.company
    )

    user_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        index=True,
        tracking=True,
        default=lambda self: self.env.user,
        domain=lambda self: [('groups_id', 'in', self.env.ref('sales_team.group_sale_salesman').id)]
    )

    team_id = fields.Many2one(
        'crm.team',
        'Sales Team',
        readonly=True,
        states={'draft': [('readonly', False)]},
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]"
    )

    # Computed Fields - Fehlertolerant

    original_uom_qty = fields.Float(
    string='Original Quantity',
    compute='_compute_uom_qty',
    store=True
    )
    
    amount_untaxed = fields.Monetary(
        string='Untaxed Amount',
        store=True,
        readonly=True,
        compute='_compute_amount_all',
        tracking=True
    )

    amount_tax = fields.Monetary(
        string='Taxes',
        store=True,
        readonly=True,
        compute='_compute_amount_all'
    )

    amount_total = fields.Monetary(
        string='Total',
        store=True,
        readonly=True,
        compute='_compute_amount_all',
        tracking=True
    )

    # Progress Tracking
    order_line_count = fields.Integer(
        string='Order Line Count',
        compute='_compute_order_line_count'
    )

    sale_order_count = fields.Integer(
        string='Sale Orders',
        compute='_compute_sale_order_count'
    )


    @api.depends("line_ids.price_total")
    def _compute_amount_all(self):
        """
        Fehlertoleante Berechnung aller Beträge.

        Anwendungsbeispiel:
        - Graceful Handling bei fehlenden Linien
        - Robuste Währungsberechnung
        - Sichere Steuerberechnung
        """
        for order in self:
            try:
                amount_untaxed = amount_tax = 0.0

                for line in order.line_ids:
                    try:
                        amount_untaxed += line.price_subtotal or 0.0
                        amount_tax += line.price_tax or 0.0
                    except Exception as line_error:
                        _logger.warning(
                            "Fehler bei Berechnung Line %s: %s",
                            line.id, str(line_error)
                        )
                        continue

                order.update({
                    'amount_untaxed': amount_untaxed,
                    'amount_tax': amount_tax,
                    'amount_total': amount_untaxed + amount_tax,
                })

            except Exception as e:
                _logger.error(
                    "Fehler bei _compute_amount_all für Order %s: %s",
                    order.name, str(e)
                )
                order.update({
                    'amount_untaxed': 0.0,
                    'amount_tax': 0.0,
                    'amount_total': 0.0,
                })

    @api.depends('line_ids')
    def _compute_order_line_count(self):
        """Fehlertoleante Berechnung der Zeilenanzahl"""
        for order in self:
            try:
                order.order_line_count = len(order.line_ids)
            except Exception as e:
                _logger.warning(
                    "Fehler bei _compute_order_line_count: %s", str(e)
                )
                order.order_line_count = 0

    def _compute_sale_order_count(self):
        """Berechnung verknüpfter Sale Orders"""
        for order in self:
            try:
                # Suche Sale Orders die von diesem Blanket Order erstellt wurden
                sale_orders = self.env['sale.order'].search([
                    ('origin', '=', order.name)
                ])
                order.sale_order_count = len(sale_orders)
            except Exception as e:
                _logger.warning(
                    "Fehler bei _compute_sale_order_count: %s", str(e)
                )
                order.sale_order_count = 0

    # OnChange Methoden

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """
        Partner-Änderung - Fehlertolerant

        Anwendungsbeispiel:
        - Automatische Adress-Updates
        - Pricelist-Synchronisation
        - Payment Terms Update
        """
        if not self.partner_id:
            return

        try:
            # Adressen aktualisieren
            addr = self.partner_id.address_get(['delivery', 'invoice'])

            values = {
                'partner_invoice_id': addr.get('invoice', self.partner_id.id),
                'partner_shipping_id': addr.get('delivery', self.partner_id.id),
            }

            # Pricelist aktualisieren
            if hasattr(self.partner_id, 'property_product_pricelist'):
                pricelist = self.partner_id.property_product_pricelist
                if pricelist and pricelist.Active:
                    values['pricelist_id'] = pricelist.id
                elif not self.pricelist_id:
                    # Fallback zur Standard-Pricelist
                    default_pricelist = self.env['product.pricelist'].search([
                        ('company_id', '=', self.company_id.id)
                    ], limit=1)
                    if default_pricelist:
                        values['pricelist_id'] = default_pricelist.id

            # Payment Terms
            if hasattr(self.partner_id, 'property_payment_term_id'):
                payment_term = self.partner_id.property_payment_term_id
                if payment_term:
                    values['payment_term_id'] = payment_term.id

            # Sales Team
            if hasattr(self.partner_id, 'team_id'):
                team = self.partner_id.team_id
                if team:
                    values['team_id'] = team.id

            self.update(values)

        except Exception as e:
            _logger.warning(
                "Fehler bei _onchange_partner_id: %s", str(e)
            )




    def _compute_uom_qty(self):
        for bo in self:
            bo.original_uom_qty = sum(bo.mapped("line_ids.original_uom_qty"))
            bo.ordered_uom_qty = sum(bo.mapped("line_ids.ordered_uom_qty"))
            bo.invoiced_uom_qty = sum(bo.mapped("line_ids.invoiced_uom_qty"))
            bo.delivered_uom_qty = sum(bo.mapped("line_ids.delivered_uom_qty"))
            bo.remaining_uom_qty = sum(bo.mapped("line_ids.remaining_uom_qty"))

    @api.model_create_multi
    def create(self, vals_list):
        """Fehlertoleante Erstellung mit Sequenz-Generierung"""
        for vals in vals_list:
            try:
                if vals.get('name', _('New')) == _('New'):
                    seq_date = None
                    if 'date_order' in vals:
                        seq_date = fields.Datetime.context_timestamp(
                            self, fields.Datetime.to_datetime(vals['date_order'])
                        )

                    # Sequenz generieren
                    vals['name'] = self.env['ir.sequence'].next_by_code(
                        'sale.blanket.order', sequence_date=seq_date
                    ) or _('New')

            except Exception as e:
                _logger.error(
                    "Fehler bei Sequenz-Generierung: %s", str(e)
                )
                vals['name'] = f"BO{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"

        return super().create(vals_list)

    def write(self, vals):
        """Fehlertoleante Aktualisierung mit State-Validierung"""
        try:
            # State-Änderungen tracken
            if 'state' in vals:
                for order in self:
                    old_state = order.state
                    new_state = vals['state']
                    _logger.info(
                        "Blanket Order %s: %s → %s",
                        order.name, old_state, new_state
                    )

            return super().write(vals)

        except Exception as e:
            _logger.error(
                "Fehler bei write für Orders %s: %s",
                self.mapped('name'), str(e)
            )
            raise UserError(
                _("Error updating blanket order: %s") % str(e)
            )

    # BUSINESS METHODS
    # ===================================================================

    def action_confirm(self):
        """
        Blanket Order bestätigen - Idempotent

        Anwendungsbeispiel:
        - Mehrfache Ausführung safe
        - Validierung vor Bestätigung
        - Robuste State-Transition
        """
        for order in self:
            try:
                # Bereits bestätigt? → Skip
                if order.state != 'draft':
                    _logger.info(
                        "Order %s bereits bestätigt (State: %s)",
                        order.name, order.state
                    )
                    continue

                # Validierung
                if not order.line_ids:
                    raise UserError(
                        _("Cannot confirm blanket order without lines!")
                    )

                # Bestätigen
                order.state = 'open'
                order.message_post(
                    body=_("Blanket order confirmed."),
                    subtype_xmlid='mail.mt_comment'
                )

                _logger.info("Order %s erfolgreich bestätigt", order.name)

            except Exception as e:
                _logger.error(
                    "Fehler bei action_confirm für %s: %s",
                    order.name, str(e)
                )
                raise UserError(
                    _("Error confirming blanket order %s: %s")
                    % (order.name, str(e))
                )

    def action_cancel(self):
        """Order stornieren - Idempotent"""
        for order in self:
            try:
                if order.state == 'cancel':
                    continue

                order.state = 'cancel'
                order.message_post(
                    body=_("Blanket order cancelled."),
                    subtype_xmlid='mail.mt_comment'
                )

            except Exception as e:
                _logger.error(
                    "Fehler bei action_cancel: %s", str(e)
                )

    def action_set_to_draft(self):
        """Zurück zu Draft - Validiert"""
        for order in self:
            try:
                # Prüfe ob Sale Orders existieren
                sale_orders = self.env['sale.order'].search([
                    ('origin', '=', order.name),
                    ('state', '!=', 'cancel')
                ])

                if sale_orders:
                    raise UserError(
                        _("Cannot reset to draft: Active sale orders exist!")
                    )

                order.state = 'draft'

            except Exception as e:
                _logger.error(
                    "Fehler bei action_set_to_draft: %s", str(e)
                )
                raise


    @api.model
    def expire_orders(self):
        """
        Cron Job: Blanket Orders expirieren

        Anwendungsbeispiel:
        - Täglicher Cron-Lauf
        - Automatische Expiration basierend auf Datum
        - Robuste Batch-Verarbeitung
        """
        try:
            today = fields.Date.today(self)

            orders_to_expire = self.search([
                ('state', '=', 'open'),
                ('validity_date', '<', today)
            ])

            for order in orders_to_expire:
                try:
                    order.state = 'expired'
                    order.message_post(
                        body=_("Blanket order automatically expired."),
                        subtype_xmlid='mail.mt_comment'
                    )
                    _logger.info("Order %s expired", order.name)

                except Exception as e:
                    _logger.error(
                        "Fehler beim Expirieren von %s: %s",
                        order.name, str(e)
                    )

            _logger.info(
                "Expire Orders Cron: %d orders processed",
                len(orders_to_expire)
            )

        except Exception as e:
            _logger.error("Fehler im expire_orders Cron: %s", str(e))



    def action_view_sale_orders(self):
        """Action für verknüpfte Sale Orders"""
        try:
            sale_orders = self.env['sale.order'].search([
                ('origin', '=', self.name)
            ])

            return {
                'type': 'ir.actions.act_window',
                'name': _('Sale Orders from %s') % self.name,
                'view_mode': 'tree,form',
                'res_model': 'sale.order',
                'domain': [('id', 'in', sale_orders.ids)],
                'context': {
                    'default_origin': self.name,
                    'from_blanket_order': True,
                }
            }

        except Exception as e:
            _logger.error("Fehler bei action_view_sale_orders: %s", str(e))
            raise UserError(_("Error viewing sale orders: %s") % str(e))

    def action_create_sale_order(self):
        """Action für Sale Order Wizard"""
        try:
            if self.state != 'open':
                raise UserError(
                    _("Can only create sale orders from open blanket orders!")
                )

            return {
                'type': 'ir.actions.act_window',
                'name': _('Create Sale Order'),
                'view_mode': 'form',
                'res_model': 'sale.blanket.order.wizard',
                'target': 'new',
                'context': {
                    'default_blanket_order_id': self.id,
                    'active_model': 'sale.blanket.order',
                    'active_id': self.id,
                    'active_ids': [self.id],
                }
            }

        except Exception as e:
            _logger.error("Fehler bei action_create_sale_order: %s", str(e))
            raise UserError(_("Error creating sale order: %s") % str(e))

    # CONSTRAINTS AND VALIDATIONS
    # ===================================================================

    @api.constrains('validity_date', 'date_order')
    def _check_validity_date(self):
        """Validierung Gültigkeitsdatum"""
        for order in self:
            if order.validity_date and order.date_order:
                if order.validity_date < order.date_order.date():
                    raise ValidationError(
                        _("Validity date cannot be before order date!")
                    )

    @api.constrains('line_ids')
    def _check_line_ids(self):
        """Validierung Order Lines"""
        for order in self:
            if order.state == 'open' and not order.line_ids:
                raise ValidationError(
                    _("Open blanket orders must have at least one line!")
                )

    def name_get(self):
        """Erweiterte Anzeige mit Partner-Info"""
        result = []
        for order in self:
            try:
                name = order.name
                if order.partner_id:
                    name = f"{order.name} - {order.partner_id.name}"
                result.append((order.id, name))
            except Exception as e:
                _logger.warning("Fehler bei name_get: %s", str(e))
                result.append((order.id, order.name or 'Draft Order'))

        return result
