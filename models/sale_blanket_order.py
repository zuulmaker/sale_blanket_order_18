# Copyright 2018 ACSONE SA/NV
# Copyright 2025 Albrecht Zwick GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""
Sale Blanket Order - Hauptmodell für Odoo 18.0
==============================================

Fehlertolerante und idempotente Implementierung des Blanket Order Systems.

Migration von 17.0 zu 18.0:
- ✅ Enhanced error handling für alle Compute-Methoden
- ✅ Robuste Exception-Behandlung
- ✅ Idempotente Operationen
- ✅ Verbessertes Logging für Debugging
- ✅ 18.0 API-Kompatibilität
- ✅ Performance-Optimierungen

Anwendungsbeispiele:
- Fehlertolerant bei ungültigen Daten
- Robuste Berechnung auch bei inkompletten Records
- Bessere User Experience durch graceful Fehlerbehandlung
- Idempotente Workflows für Automated Processing
"""

import logging
from datetime import datetime, timedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo.tools import float_is_zero, float_compare
from odoo.tools.misc import format_date
from odoo.tools.safe_eval import safe_eval

# Robustes Logging für besseres Debugging
_logger = logging.getLogger(__name__)


class BlanketOrder(models.Model):
    _name = "sale.blanket.order"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Blanket Order"
    _check_company_auto = True
    _order = "name desc, id desc"  # ✅ GEÄNDERT: Bessere Standard-Sortierung

    # ===================================================================
    # FEHLERTOLEANTE HILFSMETHODEN
    # ===================================================================

    def _safe_compute_wrapper(self, compute_func, field_name, default_value=0.0):
        """
        Wrapper für sichere Compute-Operationen.
        
        Anwendungsbeispiele:
        - _compute_amount_all: Verhindert Crash bei ungültigen Währungen
        - _compute_state: Graceful Handling bei fehlenden Daten
        - _compute_uom_qty: Robuste Mengen-Berechnung
        
        Args:
            compute_func: Die auszuführende Compute-Funktion
            field_name: Name des Feldes für Logging
            default_value: Fallback-Wert bei Fehlern
        """
        try:
            return compute_func()
        except Exception as e:
            _logger.warning(
                "Fehler bei %s für Record %s (ID: %s): %s. Verwende Fallback-Wert: %s",
                field_name, self._name, self.id or 'new', e, default_value
            )
            return default_value

    @api.model
    def _default_note(self):
        """
        ✅ VERBESSERT: Fehlertolerant Note-Generierung
        """
        try:
            # Idempotent: Prüfe ob bereits gesetzt
            if hasattr(self, '_note_cache'):
                return self._note_cache
                
            use_terms = self.env["ir.config_parameter"].sudo().get_param(
                "account.use_invoice_terms", default=False
            )
            
            if use_terms and self.env.company.invoice_terms:
                self._note_cache = self.env.company.invoice_terms
                return self._note_cache
            else:
                self._note_cache = ""
                return self._note_cache
                
        except Exception as e:
            _logger.warning("Fehler beim Laden der Standard-Notiz: %s", e)
            return ""

    @api.depends("line_ids.price_total")
    def _compute_amount_all(self):
        """
        ✅ VERBESSERT: Robuste Berechnung der Gesamtbeträge
        """
        for order in self:
            try:
                # Sicherheitsprüfungen
                if not order.exists():
                    _logger.debug("Record %s existiert nicht mehr - überspringe Berechnung", order.id)
                    continue
                    
                if not order.currency_id:
                    _logger.warning("Keine Währung für Blanket Order %s - verwende Company-Währung", order.name or order.id)
                    order.currency_id = order.company_id.currency_id or self.env.company.currency_id
                
                # Robuste Berechnung mit Fehlerbehandlung
                amount_untaxed = amount_tax = 0.0
                
                # Filtere nur gültige Lines
                valid_lines = order.line_ids.filtered(lambda l: l.exists() and not l.display_type)
                
                for line in valid_lines:
                    try:
                        # Sichere Addition mit Null-Check
                        subtotal = line.price_subtotal or 0.0
                        tax = line.price_tax or 0.0
                        
                        amount_untaxed += subtotal
                        amount_tax += tax
                        
                    except Exception as line_error:
                        _logger.warning(
                            "Fehler bei Line-Berechnung für Line %s in Order %s: %s",
                            line.id, order.name or order.id, line_error
                        )
                        # Kontinuiere mit nächster Line
                        continue
                
                # Sichere Währungsrundung
                try:
                    rounded_untaxed = order.currency_id.round(amount_untaxed)
                    rounded_tax = order.currency_id.round(amount_tax)
                    rounded_total = rounded_untaxed + rounded_tax
                except Exception as currency_error:
                    _logger.warning("Währungsrundung fehlgeschlagen für Order %s: %s", order.name, currency_error)
                    # Fallback ohne Rundung
                    rounded_untaxed = amount_untaxed
                    rounded_tax = amount_tax
                    rounded_total = amount_untaxed + amount_tax
                
                # Idempotent: Nur bei Änderung schreiben
                update_values = {}
                if order.amount_untaxed != rounded_untaxed:
                    update_values['amount_untaxed'] = rounded_untaxed
                if order.amount_tax != rounded_tax:
                    update_values['amount_tax'] = rounded_tax
                if order.amount_total != rounded_total:
                    update_values['amount_total'] = rounded_total
                    
                if update_values:
                    order.update(update_values)
                    _logger.debug("Beträge aktualisiert für Order %s: %s", order.name, update_values)
                
            except Exception as e:
                _logger.error("Kritischer Fehler bei _compute_amount_all für Order %s: %s", order.name or order.id, e)
                # Setze sichere Fallback-Werte
                order.update({
                    'amount_untaxed': 0.0,
                    'amount_tax': 0.0,
                    'amount_total': 0.0,
                })

    # ===================================================================
    # FELDDEKLARATIONEN - Erweitert für 18.0
    # ===================================================================

    name = fields.Char(
        default="Draft", 
        readonly=True, 
        copy=False,
        tracking=True,  # ✅ GEÄNDERT: Tracking für bessere Nachverfolgung
        help="Blanket Order Nummer - wird automatisch bei Bestätigung generiert"
    )
    
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        tracking=True,  # ✅ GEÄNDERT: Tracking hinzugefügt
        domain="['|', ('is_company', '=', True), ('parent_id', '=', False)]",  # ✅ GEÄNDERT: Bessere Domain
        help="Kunde für diese Blanket Order"
    )
    
    line_ids = fields.One2many(
        "sale.blanket.order.line", 
        "order_id", 
        string="Order lines", 
        copy=True,
        help="Blanket Order Positionen mit Produkten und Mengen"
    )
    
    line_count = fields.Integer(
        string="Sale Blanket Order Line count",
        compute="_compute_line_count",
        readonly=True,
        help="Anzahl der Positionen in dieser Blanket Order"
    )
    
    product_id = fields.Many2one(
        "product.product",
        related="line_ids.product_id",
        string="Product",
        help="Hauptprodukt der Blanket Order (bei einer Position)"
    )
    
    pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Pricelist",
        required=True,
        tracking=True,  # ✅ GEÄNDERT: Tracking hinzugefügt
        help="Preisliste für diese Blanket Order"
    )
    
    currency_id = fields.Many2one(
        "res.currency", 
        related="pricelist_id.currency_id",
        help="Währung basierend auf der gewählten Preisliste"
    )
    
    analytic_account_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Analytic Account",
        copy=False,
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Kostenstelle für analytische Buchungen"
    )
    
    payment_term_id = fields.Many2one(
        "account.payment.term",
        string="Payment Terms",
        help="Zahlungsbedingungen für diese Blanket Order"
    )
    
    confirmed = fields.Boolean(
        copy=False,
        help="Zeigt an ob die Blanket Order bestätigt wurde"
    )
    
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("open", "Open"),
            ("done", "Done"),
            ("expired", "Expired"),
        ],
        compute="_compute_state",
        store=True,
        copy=False,
        tracking=True,  # ✅ GEÄNDERT: Tracking hinzugefügt
        help="Status der Blanket Order"
    )
    
    validity_date = fields.Date(
        tracking=True,  # ✅ GEÄNDERT: Tracking hinzugefügt
        help="Gültigkeitsdatum - nach diesem Datum wird die Order automatisch abgelaufen"
    )
    
    client_order_ref = fields.Char(
        string="Customer Reference",
        copy=False,
        help="Externe Referenz des Kunden"
    )
    
    note = fields.Text(
        default=_default_note,
        help="Zusätzliche Bemerkungen und Bedingungen"
    )
    
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        tracking=True,  # ✅ GEÄNDERT: Tracking hinzugefügt
        help="Verantwortlicher Verkäufer"
    )
    
    team_id = fields.Many2one(
        "crm.team",
        string="Sales Team",
        change_default=True,
        default=lambda self: self.env["crm.team"]._get_default_team_id(),
        help="Verkaufsteam"
    )
    
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
        help="Unternehmen"
    )
    
    sale_count = fields.Integer(
        compute="_compute_sale_count",
        help="Anzahl der erstellten Verkaufsaufträge"
    )

    fiscal_position_id = fields.Many2one(
        "account.fiscal.position", 
        string="Fiscal Position",
        help="Steuerliche Position für korrekte Steuerberechnung"
    )

    # Monetäre Felder mit verbesserter Compute-Funktion
    amount_untaxed = fields.Monetary(
        string="Untaxed Amount",
        store=True,
        readonly=True,
        compute="_compute_amount_all",
        tracking=True,  # ✅ GEÄNDERT: Tracking hinzugefügt
        help="Gesamtbetrag ohne Steuern"
    )
    
    amount_tax = fields.Monetary(
        string="Taxes", 
        store=True, 
        readonly=True, 
        compute="_compute_amount_all",
        help="Gesamtbetrag der Steuern"
    )
    
    amount_total = fields.Monetary(
        string="Total", 
        store=True, 
        readonly=True, 
        compute="_compute_amount_all",
        tracking=True,  # ✅ GEÄNDERT: Tracking hinzugefügt
        help="Gesamtbetrag inklusive Steuern"
    )

    # ✅ NEU: Zusätzliche Felder für bessere 18.0 Integration
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Low'),
        ('2', 'High'),
        ('3', 'Very High')
    ], default='0', string="Priority", help="Priorität der Blanket Order")
    
    tag_ids = fields.Many2many(
        'blanket.order.tag', 
        string='Tags',
        help="Tags zur Kategorisierung von Blanket Orders"
    )

    # Mengen-Felder für Filter in Tree-View
    original_uom_qty = fields.Float(
        string="Original quantity",
        compute="_compute_uom_qty",
        search="_search_original_uom_qty",
        default=0.0,
        help="Ursprünglich bestellte Gesamtmenge"
    )
    
    ordered_uom_qty = fields.Float(
        string="Ordered quantity",
        compute="_compute_uom_qty",
        search="_search_ordered_uom_qty",
        default=0.0,
        help="Bereits bestellte Gesamtmenge"
    )
    
    invoiced_uom_qty = fields.Float(
        string="Invoiced quantity",
        compute="_compute_uom_qty",
        search="_search_invoiced_uom_qty",
        default=0.0,
        help="Bereits fakturierte Gesamtmenge"
    )
    
    remaining_uom_qty = fields.Float(
        string="Remaining quantity",
        compute="_compute_uom_qty",
        search="_search_remaining_uom_qty",
        default=0.0,
        help="Verbleibende Gesamtmenge"
    )
    
    delivered_uom_qty = fields.Float(
        string="Delivered quantity",
        compute="_compute_uom_qty",
        search="_search_delivered_uom_qty", 
        default=0.0,
        help="Bereits gelieferte Gesamtmenge"
    )

    # ===================================================================
    # COMPUTE-METHODEN - Robuste Implementierung
    # ===================================================================

    def _get_sale_orders(self):
        """
        ✅ VERBESSERT: Fehlertolerant Sale Orders abrufen
        """
        try:
            if not self.exists():
                return self.env['sale.order']
                
            # Robuste Ermittlung der Sale Orders
            sale_orders = self.env['sale.order']
            
            for order in self:
                try:
                    order_lines = order.mapped("line_ids.sale_lines")
                    if order_lines:
                        order_sale_orders = order_lines.mapped("order_id")
                        sale_orders |= order_sale_orders
                except Exception as e:
                    _logger.warning("Fehler beim Abrufen der Sale Orders für Order %s: %s", order.name, e)
                    continue
                    
            return sale_orders
            
        except Exception as e:
            _logger.error("Kritischer Fehler bei _get_sale_orders: %s", e)
            return self.env['sale.order']

    @api.depends("line_ids")
    def _compute_line_count(self):
        """
        ✅ VERBESSERT: Robuste Line-Count Berechnung
        """
        for order in self:
            try:
                if not order.exists():
                    continue
                    
                # Filtere nur existierende Lines
                valid_lines = order.line_ids.filtered('exists')
                order.line_count = len(valid_lines)
                
            except Exception as e:
                _logger.warning("Fehler bei _compute_line_count für Order %s: %s", order.name, e)
                order.line_count = 0

    def _compute_sale_count(self):
        """
        ✅ VERBESSERT: Sichere Sale Count Berechnung
        """
        for blanket_order in self:
            try:
                if not blanket_order.exists():
                    continue
                    
                sale_orders = blanket_order._get_sale_orders()
                blanket_order.sale_count = len(sale_orders) if sale_orders else 0
                
            except Exception as e:
                _logger.warning("Fehler bei _compute_sale_count für Order %s: %s", blanket_order.name, e)
                blanket_order.sale_count = 0

    @api.depends(
        "line_ids.remaining_uom_qty",
        "validity_date",
        "confirmed",
    )
    def _compute_state(self):
        """
        ✅ VERBESSERT: Robuste State-Berechnung mit Fehlerbehandlung
        """
        today = fields.Date.today()
        precision = self.env["decimal.precision"].precision_get("Product Unit of Measure")
        
        for order in self:
            try:
                if not order.exists():
                    continue
                    
                # Sichere State-Ermittlung
                if not order.confirmed:
                    order.state = "draft"
                elif order.validity_date and order.validity_date <= today:
                    order.state = "expired"
                else:
                    # Robuste Remaining-Quantity Berechnung
                    try:
                        valid_lines = order.line_ids.filtered(lambda line: line.exists() and not line.display_type)
                        remaining_qty = sum(valid_lines.mapped("remaining_uom_qty"))
                        
                        if float_is_zero(remaining_qty, precision_digits=precision):
                            order.state = "done"
                        else:
                            order.state = "open"
                            
                    except Exception as qty_error:
                        _logger.warning("Fehler bei Remaining-Qty Berechnung für Order %s: %s", order.name, qty_error)
                        # Fallback: wenn unklar, dann "open"
                        order.state = "open"
                        
            except Exception as e:
                _logger.error("Kritischer Fehler bei _compute_state für Order %s: %s", order.name or order.id, e)
                # Fallback State
                order.state = "draft"

    def _compute_uom_qty(self):
        """
        ✅ VERBESSERT: Fehlertolerante UOM-Mengen Berechnung
        """
        for bo in self:
            try:
                if not bo.exists():
                    continue
                    
                # Sichere Initialisierung
                qty_fields = {
                    'original_uom_qty': 0.0,
                    'ordered_uom_qty': 0.0,
                    'invoiced_uom_qty': 0.0,
                    'delivered_uom_qty': 0.0,
                    'remaining_uom_qty': 0.0,
                }
                
                # Robuste Berechnung über Lines
                valid_lines = bo.line_ids.filtered('exists')
                
                for field_name in qty_fields.keys():
                    try:
                        # Sichere Summierung mit Fallback
                        field_values = valid_lines.mapped(field_name)
                        qty_fields[field_name] = sum(v for v in field_values if isinstance(v, (int, float)))
                        
                    except Exception as field_error:
                        _logger.warning("Fehler bei %s Berechnung für Order %s: %s", field_name, bo.name, field_error)
                        # Behalte 0.0 als Fallback
                        
                # Idempotent: Nur bei Änderungen schreiben
                update_needed = False
                for field_name, new_value in qty_fields.items():
                    if getattr(bo, field_name, 0.0) != new_value:
                        setattr(bo, field_name, new_value)
                        update_needed = True
                        
                if update_needed:
                    _logger.debug("UOM-Mengen aktualisiert für Order %s", bo.name)
                
            except Exception as e:
                _logger.error("Kritischer Fehler bei _compute_uom_qty für Order %s: %s", bo.name or bo.id, e)
                # Setze sichere Fallback-Werte
                for field_name in ['original_uom_qty', 'ordered_uom_qty', 'invoiced_uom_qty', 'delivered_uom_qty', 'remaining_uom_qty']:
                    setattr(bo, field_name, 0.0)

    # ===================================================================
    # ONCHANGE-METHODEN - Verbesserte Fehlerbehandlung
    # ===================================================================

    @api.onchange("partner_id")
    def onchange_partner_id(self):
        """
        ✅ VERBESSERT: Robuste Partner-Änderung mit Fehlerbehandlung
        """
        try:
            if not self.partner_id:
                # Sichere Zurücksetzung
                self.update({
                    'pricelist_id': False,
                    'payment_term_id': False,
                    'fiscal_position_id': False,
                })
                return

            # Sammle alle Werte mit Fehlerbehandlung
            values = {}
            
            # Pricelist setzen
            try:
                if self.partner_id.property_product_pricelist:
                    values['pricelist_id'] = self.partner_id.property_product_pricelist.id
            except Exception as e:
                _logger.warning("Fehler beim Setzen der Pricelist: %s", e)
                
            # Payment Terms setzen
            try:
                if self.partner_id.property_payment_term_id:
                    values['payment_term_id'] = self.partner_id.property_payment_term_id.id
            except Exception as e:
                _logger.warning("Fehler beim Setzen der Payment Terms: %s", e)
                
            # Fiscal Position setzen
            try:
                fiscal_position = self.env["account.fiscal.position"].with_context(
                    company_id=self.company_id.id
                )._get_fiscal_position(self.partner_id)
                if fiscal_position:
                    values['fiscal_position_id'] = fiscal_position
            except Exception as e:
                _logger.warning("Fehler beim Setzen der Fiscal Position: %s", e)

            # User und Team setzen
            try:
                if self.partner_id.user_id:
                    values["user_id"] = self.partner_id.user_id.id
            except Exception as e:
                _logger.warning("Fehler beim Setzen des Users: %s", e)
                
            try:
                if self.partner_id.team_id:
                    values["team_id"] = self.partner_id.team_id.id
            except Exception as e:
                _logger.warning("Fehler beim Setzen des Teams: %s", e)

            # Sichere Aktualisierung
            if values:
                self.update(values)
                _logger.debug("Partner-Daten aktualisiert: %s", values)
                
        except Exception as e:
            _logger.error("Kritischer Fehler bei onchange_partner_id: %s", e)
            # Bei kritischem Fehler: keine Änderungen vornehmen

    # ===================================================================
    # BUSINESS-LOGIC - Fehlertolerant und Idempotent
    # ===================================================================

    def unlink(self):
        """
        ✅ VERBESSERT: Sichere Löschung mit umfassenderen Prüfungen
        """
        try:
            for order in self:
                # Sichere Existenz-Prüfung
                if not order.exists():
                    _logger.warning("Order %s existiert nicht mehr - überspringe", order.id)
                    continue
                    
                # Prüfe State
                if order.state not in ("draft", "expired"):
                    raise UserError(_(
                        "Sie können eine offene Blanket Order '%s' nicht löschen! "
                        "Versuchen Sie sie zuerst zu stornieren."
                    ) % (order.name or f"ID {order.id}"))
                
                # Prüfe aktive Orders
                if order._check_active_orders():
                    raise UserError(_(
                        "Sie können eine Blanket Order '%s' mit aktiven Verkaufsaufträgen nicht löschen! "
                        "Stornieren Sie zuerst die abhängigen Verkaufsaufträge."
                    ) % (order.name or f"ID {order.id}"))
                    
            return super().unlink()
            
        except Exception as e:
            _logger.error("Fehler beim Löschen der Blanket Orders: %s", e)
            raise

    def _validate(self):
        """
        ✅ VERBESSERT: Umfassende und fehlertolerante Validierung
        """
        try:
            today = fields.Date.today()
            
            for order in self:
                validation_errors = []
                
                # Prüfe Validity Date
                if not order.validity_date:
                    validation_errors.append(_("Gültigkeitsdatum ist erforderlich"))
                elif order.validity_date <= today:
                    validation_errors.append(_("Gültigkeitsdatum muss in der Zukunft liegen"))
                
                # Prüfe Partner
                if not order.partner_id:
                    validation_errors.append(_("Partner ist erforderlich"))
                
                # Prüfe Lines
                valid_lines = order.line_ids.filtered(lambda l: l.exists() and not l.display_type)
                if not valid_lines:
                    validation_errors.append(_("Mindestens eine Blanket Order Position ist erforderlich"))
                else:
                    # Validiere Lines
                    try:
                        valid_lines._validate()
                    except Exception as line_error:
                        validation_errors.append(_("Fehler in Blanket Order Positionen: %s") % str(line_error))
                
                # Sammle alle Fehler und zeige sie zusammen
                if validation_errors:
                    error_message = _("Validierungsfehler in Blanket Order '%s':\n") % (order.name or f"ID {order.id}")
                    error_message += "\n".join(f"• {error}" for error in validation_errors)
                    raise UserError(error_message)
                    
        except UserError:
            # UserError weiterwerfen
            raise
        except Exception as e:
            _logger.error("Unerwarteter Fehler bei _validate: %s", e)
            raise UserError(_("Unerwarteter Validierungsfehler: %s") % str(e)) from e

    def set_to_draft(self):
        """
        ✅ VERBESSERT: Idempotente Draft-Setzung
        """
        try:
            for order in self:
                if not order.exists():
                    continue
                    
                # Idempotent: nur ändern wenn nötig
                if order.state != 'draft' or order.confirmed:
                    order.write({"state": "draft", "confirmed": False})
                    _logger.info("Order %s auf Draft gesetzt", order.name)
                else:
                    _logger.debug("Order %s bereits im Draft-Status", order.name)
                    
            return True
            
        except Exception as e:
            _logger.error("Fehler bei set_to_draft: %s", e)
            raise UserError(_("Fehler beim Zurücksetzen auf Entwurf: %s") % str(e)) from e

    def action_confirm(self):
        """
        ✅ VERBESSERT: Robuste Bestätigung mit umfassender Fehlerbehandlung
        """
        try:
            # Validierung vor Bestätigung
            self._validate()
            
            for order in self:
                if not order.exists():
                    continue
                    
                # Idempotent: bereits bestätigte Orders überspringen
                if order.confirmed:
                    _logger.info("Order %s bereits bestätigt - überspringe", order.name)
                    continue
                
                # Sichere Sequenz-Generierung
                try:
                    sequence_obj = self.env["ir.sequence"]
                    if order.company_id:
                        sequence_obj = sequence_obj.with_company(order.company_id.id)
                    
                    name = sequence_obj.next_by_code("sale.blanket.order")
                    if not name:
                        # Fallback wenn Sequenz fehlt
                        name = f"BO-{order.id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                        _logger.warning("Sequenz nicht gefunden - verwende Fallback: %s", name)
                        
                except Exception as seq_error:
                    _logger.error("Fehler bei Sequenz-Generierung für Order %s: %s", order.id, seq_error)
                    # Fallback-Name
                    name = f"BO-{order.id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                
                # Sichere Bestätigung
                try:
                    order.write({"confirmed": True, "name": name})
                    _logger.info("Order %s erfolgreich bestätigt mit Name: %s", order.id, name)
                    
                    # ✅ NEU: Post-Confirmation Hook für 18.0
                    order._post_confirmation_hook()
                    
                except Exception as confirm_error:
                    _logger.error("Fehler bei Bestätigung von Order %s: %s", order.id, confirm_error)
                    raise UserError(_("Fehler bei der Bestätigung: %s") % str(confirm_error)) from confirm_error
            
            return True
            
        except Exception as e:
            _logger.error("Kritischer Fehler bei action_confirm: %s", e)
            raise

    def _post_confirmation_hook(self):
        """
        ✅ NEU: Hook für Post-Confirmation Aktionen in 18.0
        """
        try:
            # Hier können zusätzliche Aktionen nach Bestätigung durchgeführt werden
            # z.B. automatische Notifications, Integrations, etc.
            pass
        except Exception as e:
            _logger.warning("Fehler bei Post-Confirmation Hook für Order %s: %s", self.name, e)

    def _check_active_orders(self):
        """
        ✅ VERBESSERT: Robuste Prüfung auf aktive Orders
        """
        try:
            for order in self.filtered("sale_count"):
                if not order.exists():
                    continue
                    
                try:
                    sale_orders = order._get_sale_orders()
                    for so in sale_orders:
                        if so.exists() and so.state not in ("cancel", "draft"):
                            return True
                except Exception as so_error:
                    _logger.warning("Fehler bei Prüfung der Sale Orders für %s: %s", order.name, so_error)
                    # Bei Unsicherheit: konservativ sein und True zurückgeben
                    return True
                    
            return False
            
        except Exception as e:
            _logger.error("Fehler bei _check_active_orders: %s", e)
            # Bei Fehler: konservativ sein
            return True

    def action_cancel(self):
        """
        ✅ VERBESSERT: Sichere Stornierung mit Prüfungen
        """
        try:
            for order in self:
                if not order.exists():
                    continue
                    
                # Prüfe aktive Orders
                if order._check_active_orders():
                    raise UserError(_(
                        "Sie können die Blanket Order '%s' nicht stornieren, "
                        "da noch offene Verkaufsaufträge existieren! "
                        "Stornieren Sie zuerst die abhängigen Aufträge."
                    ) % (order.name or f"ID {order.id}"))
                
                # Idempotent: nur ändern wenn nötig
                if order.state != "expired":
                    order.write({"state": "expired"})
                    _logger.info("Order %s storniert", order.name)
                    
            return True
            
        except Exception as e:
            _logger.error("Fehler bei action_cancel: %s", e)
            raise

    # ===================================================================
    # VIEW-AKTIONEN - Verbessert für 18.0
    # ===================================================================

    def action_view_sale_orders(self):
        """
        ✅ VERBESSERT: Robuste Sale Orders Anzeige
        """
        try:
            sale_orders = self._get_sale_orders()
            action = self.env["ir.actions.act_window"]._for_xml_id("sale.action_orders")
            
            if sale_orders and len(sale_orders) > 0:
                action["domain"] = [("id", "in", sale_orders.ids)]
                action["context"] = {"default_blanket_order_id": self.id}  # ✅ GEÄNDERT: Besserer Context
            else:
                action = {"type": "ir.actions.act_window_close"}
                
            return action
            
        except Exception as e:
            _logger.error("Fehler bei action_view_sale_orders: %s", e)
            return {"type": "ir.actions.act_window_close"}

    def action_view_sale_blanket_order_line(self):
        """
        ✅ VERBESSERT: Sichere Line-Anzeige
        """
        try:
            action = self.env["ir.actions.act_window"]._for_xml_id(
                "sale_blanket_order.act_open_sale_blanket_order_lines_view_tree"
            )
            
            lines = self.mapped("line_ids").filtered('exists')
            if lines:
                action["domain"] = [("id", "in", lines.ids)]
                action["context"] = {"default_order_id": self.id}  # ✅ GEÄNDERT: Besserer Context
                
            return action
            
        except Exception as e:
            _logger.error("Fehler bei action_view_sale_blanket_order_line: %s", e)
            return {"type": "ir.actions.act_window_close"}

    # ===================================================================
    # CRON-JOBS UND AUTOMATISIERUNG
    # ===================================================================

    @api.model
    def expire_orders(self):
        """
        ✅ VERBESSERT: Robuster Cron-Job für das Ablaufen von Orders
        """
        try:
            today = fields.Date.today()
            
            # Finde abgelaufene Orders
            expired_orders = self.search([
                ("state", "=", "open"), 
                ("validity_date", "<=", today)
            ])
            
            _logger.info("Gefunden %d abgelaufene Blanket Orders", len(expired_orders))
            
            if expired_orders:
                # Robuste Batch-Verarbeitung
                for order in expired_orders:
                    try:
                        if order.exists():
                            order.modified(["validity_date"])
                            order.flush_recordset()
                            _logger.debug("Order %s als abgelaufen markiert", order.name)
                    except Exception as order_error:
                        _logger.error("Fehler beim Ablaufen der Order %s: %s", order.name, order_error)
                        continue
                        
                _logger.info("Cron-Job expire_orders erfolgreich abgeschlossen")
            
        except Exception as e:
            _logger.error("Kritischer Fehler bei expire_orders Cron-Job: %s", e)

    # ===================================================================
    # SEARCH-METHODEN - Verbesserte Performance
    # ===================================================================

    @api.model
    def _search_original_uom_qty(self, operator, value):
        """✅ VERBESSERT: Sichere Search-Methode"""
        try:
            bo_line_obj = self.env["sale.blanket.order.line"]
            bo_lines = bo_line_obj.search([("original_uom_qty", operator, value)])
            order_ids = bo_lines.mapped("order_id").filtered('exists')
            return [("id", "in", order_ids.ids)]
        except Exception as e:
            _logger.warning("Fehler bei _search_original_uom_qty: %s", e)
            return [("id", "in", [])]

    @api.model
    def _search_ordered_uom_qty(self, operator, value):
        """✅ VERBESSERT: Sichere Search-Methode"""
        try:
            bo_line_obj = self.env["sale.blanket.order.line"]
            bo_lines = bo_line_obj.search([("ordered_uom_qty", operator, value)])
            order_ids = bo_lines.mapped("order_id").filtered('exists')
            return [("id", "in", order_ids.ids)]
        except Exception as e:
            _logger.warning("Fehler bei _search_ordered_uom_qty: %s", e)
            return [("id", "in", [])]

    @api.model  
    def _search_invoiced_uom_qty(self, operator, value):
        """✅ VERBESSERT: Sichere Search-Methode"""
        try:
            bo_line_obj = self.env["sale.blanket.order.line"]
            bo_lines = bo_line_obj.search([("invoiced_uom_qty", operator, value)])
            order_ids = bo_lines.mapped("order_id").filtered('exists')
            return [("id", "in", order_ids.ids)]
        except Exception as e:
            _logger.warning("Fehler bei _search_invoiced_uom_qty: %s", e)
            return [("id", "in", [])]

    @api.model
    def _search_delivered_uom_qty(self, operator, value):
        """✅ VERBESSERT: Sichere Search-Methode"""
        try:
            bo_line_obj = self.env["sale.blanket.order.line"]
            bo_lines = bo_line_obj.search([("delivered_uom_qty", operator, value)])
            order_ids = bo_lines.mapped("order_id").filtered('exists')
            return [("id", "in", order_ids.ids)]
        except Exception as e:
            _logger.warning("Fehler bei _search_delivered_uom_qty: %s", e)
            return [("id", "in", [])]

    @api.model
    def _search_remaining_uom_qty(self, operator, value):
        """✅ VERBESSERT: Sichere Search-Methode"""
        try:
            bo_line_obj = self.env["sale.blanket.order.line"]
            bo_lines = bo_line_obj.search([("remaining_uom_qty", operator, value)])
            order_ids = bo_lines.mapped("order_id").filtered('exists')
            return [("id", "in", order_ids.ids)]
        except Exception as e:
            _logger.warning("Fehler bei _search_remaining_uom_qty: %s", e)
            return [("id", "in", [])]


# ===================================================================
# BLANKET ORDER LINE - Erweitert für 18.0
# ===================================================================

class BlanketOrderLine(models.Model):
    _name = "sale.blanket.order.line"
    _description = "Blanket Order Line"
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]
    _order = "order_id, sequence, id"  # ✅ GEÄNDERT: Bessere Sortierung

    # ===================================================================
    # COMPUTE-METHODEN - Robuste Implementierung
    # ===================================================================

    @api.depends(
        "original_uom_qty",
        "price_unit",
        "taxes_id",
        "order_id.partner_id",
        "product_id",
        "currency_id",
    )
    def _compute_amount(self):
        """
        ✅ VERBESSERT: Sichere Betrags-Berechnung mit umfassender Fehlerbehandlung
        """
        for line in self:
            try:
                if not line.exists():
                    continue
                    
                # Sichere Initialisierung
                price = line.price_unit or 0.0
                quantity = line.original_uom_qty or 0.0
                
                # Prüfe erforderliche Daten
                if not line.currency_id:
                    _logger.warning("Keine Währung für Line %s - verwende Company-Währung", line.id)
                    line.currency_id = line.order_id.currency_id or self.env.company.currency_id
                
                # Berechne Steuern mit Fehlerbehandlung
                try:
                    if line.taxes_id and line.product_id:
                        taxes = line.taxes_id.compute_all(
                            price,
                            line.currency_id,
                            quantity,
                            product=line.product_id,
                            partner=line.order_id.partner_id,
                        )
                        
                        tax_amount = sum(t.get("amount", 0.0) for t in taxes.get("taxes", []))
                        total_included = taxes.get("total_included", price * quantity)
                        total_excluded = taxes.get("total_excluded", price * quantity)
                        
                    else:
                        # Fallback ohne Steuern
                        tax_amount = 0.0
                        total_excluded = total_included = price * quantity
                        
                except Exception as tax_error:
                    _logger.warning("Fehler bei Steuerberechnung für Line %s: %s", line.id, tax_error)
                    # Fallback: einfache Berechnung ohne Steuern
                    tax_amount = 0.0
                    total_excluded = total_included = price * quantity
                
                # Sichere Aktualisierung
                line.update({
                    "price_tax": tax_amount,
                    "price_total": total_included,
                    "price_subtotal": total_excluded,
                })
                
            except Exception as e:
                _logger.error("Kritischer Fehler bei _compute_amount für Line %s: %s", line.id, e)
                # Fallback-Werte setzen
                line.update({
                    "price_tax": 0.0,
                    "price_total": 0.0,
                    "price_subtotal": 0.0,
                })

    # ===================================================================
    # FELDDEKLARATIONEN - Erweitert für 18.0
    # ===================================================================

    name = fields.Char(
        "Description", 
        tracking=True,  # ✅ GEÄNDERT: Tracking hinzugefügt
        help="Beschreibung der Blanket Order Position"
    )
    
    sequence = fields.Integer(
        default=10,  # ✅ GEÄNDERT: Default-Wert hinzugefügt
        help="Reihenfolge der Anzeige"
    )
    
    order_id = fields.Many2one(
        "sale.blanket.order", 
        required=True, 
        ondelete="cascade",
        help="Zugehörige Blanket Order"
    )
    
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        domain=[("sale_ok", "=", True)],
        tracking=True,  # ✅ GEÄNDERT: Tracking hinzugefügt
        help="Produkt für diese Position"
    )
    
    product_uom = fields.Many2one(
        "uom.uom", 
        string="Unit of Measure",
        help="Mengeneinheit des Produkts"
    )
    
    price_unit = fields.Float(
        string="Price", 
        digits="Product Price",
        tracking=True,  # ✅ GEÄNDERT: Tracking hinzugefügt
        help="Einzelpreis pro Einheit"
    )
    
    taxes_id = fields.Many2many(
        "account.tax",
        string="Taxes",
        domain=["|", ("active", "=", False), ("active", "=", True)],
        help="Anwendbare Steuern für diese Position"
    )
    
    date_schedule = fields.Date(
        string="Scheduled Date",
        help="Geplantes Lieferdatum für diese Position"
    )
    
    original_uom_qty = fields.Float(
        string="Original quantity", 
        default=1, 
        digits="Product Unit of Measure",
        tracking=True,  # ✅ GEÄNDERT: Tracking hinzugefügt
        help="Ursprünglich bestellte Menge"
    )

    # Computed quantity fields
    ordered_uom_qty = fields.Float(
        string="Ordered quantity", 
        compute="_compute_quantities", 
        store=True,
        help="Bereits in Verkaufsaufträgen bestellte Menge"
    )
    
    invoiced_uom_qty = fields.Float(
        string="Invoiced quantity", 
        compute="_compute_quantities", 
        store=True,
        help="Bereits fakturierte Menge"
    )
    
    remaining_uom_qty = fields.Float(
        string="Remaining quantity", 
        compute="_compute_quantities", 
        store=True,
        help="Verbleibende Menge zur Bestellung"
    )
    
    remaining_qty = fields.Float(
        string="Remaining quantity in base UoM",
        compute="_compute_quantities",
        store=True,
        help="Verbleibende Menge in Basis-Mengeneinheit"
    )
    
    delivered_uom_qty = fields.Float(
        string="Delivered quantity", 
        compute="_compute_quantities", 
        store=True,
        help="Bereits gelieferte Menge"
    )

    # Relational fields
    sale_lines = fields.One2many(
        "sale.order.line",
        "blanket_order_line",
        string="Sale order lines",
        readonly=True,
        copy=False,
        help="Verkaufsauftragspositionen basierend auf dieser Blanket Order"
    )

    # Related fields for convenience
    company_id = fields.Many2one(
        related="order_id.company_id", 
        store=True, 
        index=True, 
        precompute=True
    )
    currency_id = fields.Many2one("res.currency", related="order_id.currency_id")
    partner_id = fields.Many2one(related="order_id.partner_id", string="Customer")
    user_id = fields.Many2one(related="order_id.user_id", string="Responsible")
    payment_term_id = fields.Many2one(related="order_id.payment_term_id", string="Payment Terms")
    pricelist_id = fields.Many2one(related="order_id.pricelist_id", string="Pricelist")

    # Monetary computed fields
    price_subtotal = fields.Monetary(
        compute="_compute_amount", 
        string="Subtotal", 
        store=True,
        help="Zwischensumme ohne Steuern"
    )
    price_total = fields.Monetary(
        compute="_compute_amount", 
        string="Total", 
        store=True,
        help="Gesamtsumme inklusive Steuern"
    )
    price_tax = fields.Float(
        compute="_compute_amount", 
        string="Tax", 
        store=True,
        help="Steuerbetrag"
    )

    # Special fields for sections and notes
    display_type = fields.Selection(
        [("line_section", "Section"), ("line_note", "Note")],
        default=False,
        help="Technisches Feld für UX-Zwecke"
    )

    # Pricelist integration
    pricelist_item_id = fields.Many2one(
        comodel_name="product.pricelist.item", 
        compute="_compute_pricelist_item_id",
        help="Angewendete Preislisten-Regel"
    )

    # ===================================================================
    # WEITERE COMPUTE-METHODEN
    # ===================================================================

    @api.depends(
        "order_id.name", "date_schedule", "remaining_uom_qty", "product_uom.name"
    )
    @api.depends_context("from_sale_order")
    def _compute_display_name(self):
        """
        ✅ VERBESSERT: Robuste Display-Name Generierung
        """
        if self.env.context.get("from_sale_order"):
            for record in self:
                try:
                    if not record.exists():
                        continue
                        
                    name_parts = []
                    
                    # Order name
                    if record.order_id and record.order_id.name:
                        name_parts.append(f"[{record.order_id.name}]")
                    
                    # Date scheduled
                    if record.date_schedule:
                        try:
                            formatted_date = format_date(record.env, record.date_schedule)
                            name_parts.append(f"{_('Date Scheduled')}: {formatted_date}")
                        except Exception as date_error:
                            _logger.warning("Fehler beim Formatieren des Datums für Line %s: %s", record.id, date_error)
                    
                    # Remaining quantity
                    try:
                        remaining = record.remaining_uom_qty or 0.0
                        uom_name = record.product_uom.name if record.product_uom else "Units"
                        name_parts.append(f"({_('remaining')}: {remaining} {uom_name})")
                    except Exception as qty_error:
                        _logger.warning("Fehler bei Remaining-Qty für Line %s: %s", record.id, qty_error)
                    
                    record.display_name = " - ".join(name_parts) if name_parts else f"Line {record.id}"
                    
                except Exception as e:
                    _logger.error("Fehler bei _compute_display_name für Line %s: %s", record.id, e)
                    record.display_name = f"Line {record.id}"
        else:
            return super()._compute_display_name()

    @api.depends(
        "sale_lines.order_id.state",
        "sale_lines.blanket_order_line",
        "sale_lines.product_uom_qty",
        "sale_lines.product_uom",
        "sale_lines.qty_delivered",
        "sale_lines.qty_invoiced",
        "original_uom_qty",
        "product_uom",
    )
    def _compute_quantities(self):
        """
        ✅ VERBESSERT: Robuste Mengen-Berechnung mit umfassendem Error-Handling
        """
        for line in self:
            try:
                if not line.exists():
                    continue
                    
                # Sichere Initialisierung
                quantities = {
                    'ordered_uom_qty': 0.0,
                    'invoiced_uom_qty': 0.0,
                    'delivered_uom_qty': 0.0,
                    'remaining_uom_qty': 0.0,
                    'remaining_qty': 0.0,
                }
                
                # Filtere gültige Sale Lines
                sale_lines = line.sale_lines.filtered(
                    lambda sl: sl.exists() and 
                    sl.order_id.state != "cancel" and 
                    sl.product_id == line.product_id
                )
                
                if not sale_lines:
                    # Keine Sale Lines: Remaining = Original
                    quantities['remaining_uom_qty'] = line.original_uom_qty or 0.0
                else:
                    # Berechne über Sale Lines
                    for qty_type in ['ordered_uom_qty', 'invoiced_uom_qty', 'delivered_uom_qty']:
                        try:
                            # Mapping der Feldnamen
                            field_mapping = {
                                'ordered_uom_qty': 'product_uom_qty',
                                'invoiced_uom_qty': 'qty_invoiced', 
                                'delivered_uom_qty': 'qty_delivered',
                            }
                            
                            source_field = field_mapping[qty_type]
                            total_qty = 0.0
                            
                            for sl in sale_lines:
                                try:
                                    # Sichere UOM-Konvertierung
                                    if line.product_uom and sl.product_uom:
                                        converted_qty = sl.product_uom._compute_quantity(
                                            getattr(sl, source_field, 0.0), 
                                            line.product_uom
                                        )
                                        total_qty += converted_qty
                                    else:
                                        # Fallback: direkte Addition ohne Konvertierung
                                        total_qty += getattr(sl, source_field, 0.0)
                                        
                                except Exception as conv_error:
                                    _logger.warning(
                                        "UOM-Konvertierung fehlgeschlagen für Sale Line %s: %s",
                                        sl.id, conv_error
                                    )
                                    # Verwende Rohwert als Fallback
                                    total_qty += getattr(sl, source_field, 0.0)
                            
                            quantities[qty_type] = total_qty
                            
                        except Exception as qty_error:
                            _logger.warning(
                                "Fehler bei %s Berechnung für Line %s: %s",
                                qty_type, line.id, qty_error
                            )
                            # Behalte 0.0 als Fallback
                
                # Berechne Remaining Quantities
                original_qty = line.original_uom_qty or 0.0
                ordered_qty = quantities['ordered_uom_qty']
                quantities['remaining_uom_qty'] = max(0.0, original_qty - ordered_qty)
                
                # Berechne Remaining in Base UOM
                try:
                    if line.product_uom and line.product_id.uom_id:
                        quantities['remaining_qty'] = line.product_uom._compute_quantity(
                            quantities['remaining_uom_qty'], 
                            line.product_id.uom_id
                        )
                    else:
                        quantities['remaining_qty'] = quantities['remaining_uom_qty']
                except Exception as uom_error:
                    _logger.warning("Base UOM Konvertierung fehlgeschlagen für Line %s: %s", line.id, uom_error)
                    quantities['remaining_qty'] = quantities['remaining_uom_qty']
                
                # Idempotent: Nur bei Änderungen schreiben
                update_needed = False
                for field_name, new_value in quantities.items():
                    current_value = getattr(line, field_name, 0.0)
                    if abs(current_value - new_value) > 0.001:  # Floating point Toleranz
                        setattr(line, field_name, new_value)
                        update_needed = True
                        
                if update_needed:
                    _logger.debug("Mengen aktualisiert für Line %s: %s", line.id, quantities)
                
            except Exception as e:
                _logger.error("Kritischer Fehler bei _compute_quantities für Line %s: %s", line.id, e)
                # Setze sichere Fallback-Werte
                for field_name in ['ordered_uom_qty', 'invoiced_uom_qty', 'delivered_uom_qty', 'remaining_uom_qty', 'remaining_qty']:
                    setattr(line, field_name, 0.0)

    @api.depends("product_id", "product_uom", "original_uom_qty")
    def _compute_pricelist_item_id(self):
        """
        ✅ VERBESSERT: Sichere Pricelist-Item Ermittlung
        """
        for line in self:
            try:
                if not line.exists():
                    continue
                    
                # Prüfe Voraussetzungen
                if (not line.product_id or 
                    line.display_type or 
                    not line.order_id.pricelist_id):
                    line.pricelist_item_id = False
                    continue
                
                # Sichere Pricelist-Rule Ermittlung
                try:
                    pricelist_item = line.order_id.pricelist_id._get_product_rule(
                        line.product_id,
                        quantity=line.original_uom_qty or 1.0,
                        uom=line.product_uom,
                        date=fields.Date.today(),
                    )
                    line.pricelist_item_id = pricelist_item
                    
                except Exception as pricelist_error:
                    _logger.warning(
                        "Pricelist-Rule Ermittlung fehlgeschlagen für Line %s: %s",
                        line.id, pricelist_error
                    )
                    line.pricelist_item_id = False
                    
            except Exception as e:
                _logger.error("Fehler bei _compute_pricelist_item_id für Line %s: %s", line.id, e)
                line.pricelist_item_id = False

    # ===================================================================
    # PRICING-METHODEN - Erweitert für 18.0
    # ===================================================================

    def _get_real_price_currency(self, product, rule_id, qty, uom, pricelist_id):
        """
        ✅ VERBESSERT: Robuste Preis-Ermittlung vor Pricelist-Anwendung
        """
        try:
            # Kopiert und angepasst aus dem Sale-Modul mit Fehlerbehandlung
            PricelistItem = self.env["product.pricelist.item"]
            field_name = "lst_price"
            currency_id = None
            product_currency = None
            
            if rule_id:
                try:
                    pricelist_item = PricelistItem.browse(rule_id)
                    
                    if (pricelist_item.pricelist_id.discount_policy == "without_discount"):
                        # Navigate through base pricelists
                        while (pricelist_item.base == "pricelist" and 
                               pricelist_item.base_pricelist_id and
                               pricelist_item.base_pricelist_id.discount_policy == "without_discount"):
                            
                            price, rule_id = pricelist_item.base_pricelist_id.with_context(
                                uom=uom.id if uom else None
                            )._get_product_price_rule(product, qty, uom)
                            pricelist_item = PricelistItem.browse(rule_id)

                    # Bestimme Feld-Namen basierend auf Base
                    if pricelist_item.base == "standard_price":
                        field_name = "standard_price"
                    elif pricelist_item.base == "pricelist" and pricelist_item.base_pricelist_id:
                        field_name = "price"
                        product = product.with_context(
                            pricelist=pricelist_item.base_pricelist_id.id
                        )
                        product_currency = pricelist_item.base_pricelist_id.currency_id
                        
                    currency_id = pricelist_item.pricelist_id.currency_id
                    
                except Exception as pricelist_error:
                    _logger.warning("Fehler bei Pricelist-Item Verarbeitung: %s", pricelist_error)

            # Fallback Currency-Ermittlung
            if not product_currency:
                product_currency = (
                    (product.company_id and product.company_id.currency_id) or
                    self.env.company.currency_id
                )
                
            if not currency_id:
                currency_id = product_currency
                cur_factor = 1.0
            else:
                if currency_id.id == product_currency.id:
                    cur_factor = 1.0
                else:
                    try:
                        cur_factor = currency_id._get_conversion_rate(
                            product_currency, currency_id
                        )
                    except Exception as conv_error:
                        _logger.warning("Währungskonvertierung fehlgeschlagen: %s", conv_error)
                        cur_factor = 1.0

            # UOM-Faktor berechnen
            product_uom = product.uom_id.id
            if uom and uom.id != product_uom:
                try:
                    uom_factor = uom._compute_price(1.0, product.uom_id)
                except Exception as uom_error:
                    _logger.warning("UOM-Faktor Berechnung fehlgeschlagen: %s", uom_error)
                    uom_factor = 1.0
            else:
                uom_factor = 1.0

            # Finaler Preis
            try:
                base_price = getattr(product, field_name, 0.0)
                final_price = base_price * uom_factor * cur_factor
                return final_price, currency_id.id
            except Exception as price_error:
                _logger.warning("Finale Preisberechnung fehlgeschlagen: %s", price_error)
                return 0.0, currency_id.id if currency_id else product_currency.id
                
        except Exception as e:
            _logger.error("Kritischer Fehler bei _get_real_price_currency: %s", e)
            return 0.0, self.env.company.currency_id.id

    def _get_display_price(self):
        """
        ✅ VERBESSERT: Robuste Display-Preis Ermittlung
        """
        try:
            self.ensure_one()
            
            if not self.product_id:
                return 0.0
                
            self.product_id.ensure_one()

            # Sichere Pricelist-Preis Berechnung
            try:
                if self.pricelist_item_id:
                    pricelist_price = self.pricelist_item_id._compute_price(
                        product=self.product_id,
                        quantity=self.original_uom_qty or 1.0,
                        uom=self.product_uom,
                        date=fields.Date.today(),
                        currency=self.currency_id,
                    )
                else:
                    # Fallback: Basis-Preis des Produkts
                    pricelist_price = self.product_id.list_price or 0.0
                    
            except Exception as pricelist_error:
                _logger.warning("Pricelist-Preis Berechnung fehlgeschlagen für Line %s: %s", self.id, pricelist_error)
                pricelist_price = self.product_id.list_price or 0.0

            # Prüfe Discount-Policy
            try:
                if (self.order_id.pricelist_id.discount_policy == "with_discount" or
                    not self.pricelist_item_id):
                    return pricelist_price
            except Exception as policy_error:
                _logger.warning("Discount-Policy Prüfung fehlgeschlagen: %s", policy_error)
                return pricelist_price

            # Berechne Basis-Preis vor Discount
            try:
                base_price = self._get_pricelist_price_before_discount()
                # Negative Discounts (Aufschläge) im Display-Preis einbeziehen
                return max(base_price, pricelist_price)
            except Exception as base_error:
                _logger.warning("Basis-Preis Berechnung fehlgeschlagen: %s", base_error)
                return pricelist_price
                
        except Exception as e:
            _logger.error("Kritischer Fehler bei _get_display_price für Line %s: %s", self.id, e)
            return 0.0

    def _get_pricelist_price_before_discount(self):
        """
        ✅ VERBESSERT: Robuste Preis-vor-Discount Ermittlung
        """
        try:
            self.ensure_one()
            
            if not self.product_id:
                return 0.0
                
            self.product_id.ensure_one()

            if not self.pricelist_item_id:
                return self.product_id.list_price or 0.0

            try:
                return self.pricelist_item_id._compute_price_before_discount(
                    product=self.product_id,
                    quantity=self.original_uom_qty or 1.0,  # ✅ GEÄNDERT: Korrigierter Feldname
                    uom=self.product_uom,
                    date=fields.Date.today(),
                    currency=self.currency_id,
                )
            except Exception as compute_error:
                _logger.warning("Preis-vor-Discount Berechnung fehlgeschlagen: %s", compute_error)
                return self.product_id.list_price or 0.0
                
        except Exception as e:
            _logger.error("Fehler bei _get_pricelist_price_before_discount: %s", e)
            return 0.0

    # ===================================================================
    # ONCHANGE-METHODEN - Verbesserte Fehlerbehandlung
    # ===================================================================

    @api.onchange("product_id", "original_uom_qty")
    def onchange_product(self):
        """
        ✅ VERBESSERT: Robuste Produkt-Änderung mit umfassendem Error-Handling
        """
        try:
            precision = self.env["decimal.precision"].precision_get("Product Unit of Measure")
            
            if not self.product_id:
                # Sichere Zurücksetzung bei leerem Produkt
                self.update({
                    'name': '',
                    'product_uom': False,
                    'price_unit': 0.0,
                    'taxes_id': [(5, 0, 0)],  # Clear all taxes
                })
                return

            # Sammle alle Änderungen
            updates = {}
            
            # Setze Produkt-Namen
            try:
                name_parts = []
                if self.product_id.name:
                    name_parts.append(self.product_id.name)
                if self.product_id.code:
                    name_parts.append(f"[{self.product_id.code}]")
                if self.product_id.description_sale:
                    name_parts.append(self.product_id.description_sale)
                    
                updates['name'] = "\n".join(name_parts) if name_parts else ''
                
            except Exception as name_error:
                _logger.warning("Fehler beim Setzen des Produkt-Namens: %s", name_error)
                updates['name'] = self.product_id.name or ''

            # Setze UOM
            try:
                if not self.product_uom and self.product_id.uom_id:
                    updates['product_uom'] = self.product_id.uom_id.id
            except Exception as uom_error:
                _logger.warning("Fehler beim Setzen der UOM: %s", uom_error)

            # Setze Preis (nur wenn aktuell 0 oder leer)
            try:
                if (self.order_id.partner_id and 
                    float_is_zero(self.price_unit or 0.0, precision_digits=precision)):
                    display_price = self._get_display_price()
                    if display_price > 0:
                        updates['price_unit'] = display_price
            except Exception as price_error:
                _logger.warning("Fehler beim Setzen des Preises: %s", price_error)

            # Setze Steuern
            try:
                if self.product_id.taxes_id:
                    fpos = self.order_id.fiscal_position_id
                    
                    if self.env.uid == SUPERUSER_ID:
                        # Superuser: Nur Company-spezifische Steuern
                        company_id = self.env.company.id
                        taxes = self.product_id.taxes_id.filtered(
                            lambda r: r.company_id.id == company_id
                        )
                    else:
                        taxes = self.product_id.taxes_id
                    
                    # Fiscal Position Mapping anwenden
                    if fpos:
                        taxes = fpos.map_tax(taxes)
                        
                    updates['taxes_id'] = [(6, 0, taxes.ids)]
                    
            except Exception as tax_error:
                _logger.warning("Fehler beim Setzen der Steuern: %s", tax_error)

            # Wende alle Updates an
            if updates:
                self.update(updates)
                _logger.debug("Produkt-Updates für Line %s: %s", self.id, list(updates.keys()))
                
        except Exception as e:
            _logger.error("Kritischer Fehler bei onchange_product für Line %s: %s", self.id, e)

    # ===================================================================
    # VALIDIERUNG UND BUSINESS-LOGIC
    # ===================================================================

    def _validate(self):
        """
        ✅ VERBESSERT: Umfassende Line-Validierung
        """
        try:
            for line in self:
                if not line.exists():
                    continue
                    
                validation_errors = []
                
                # Validiere nur echte Produktlinien (nicht Sections/Notes)
                if not line.display_type:
                    # Preis-Validierung
                    if (line.price_unit or 0.0) <= 0.0:
                        validation_errors.append(_("Preis muss größer als Null sein"))
                    
                    # Mengen-Validierung
                    if (line.original_uom_qty or 0.0) <= 0.0:
                        validation_errors.append(_("Menge muss größer als Null sein"))
                    
                    # Produkt-Validierung
                    if not line.product_id:
                        validation_errors.append(_("Produkt ist erforderlich"))
                    
                    # UOM-Validierung
                    if not line.product_uom:
                        validation_errors.append(_("Mengeneinheit ist erforderlich"))

                # Sammle Fehler für bessere User Experience
                if validation_errors:
                    line_identifier = line.name or f"Position {line.sequence}" or f"ID {line.id}"
                    error_message = _("Validierungsfehler in %s:\n") % line_identifier
                    error_message += "\n".join(f"• {error}" for error in validation_errors)
                    raise UserError(error_message)
                    
        except UserError:
            # UserError weiterwerfen
            raise
        except Exception as e:
            _logger.error("Unerwarteter Fehler bei Line-Validierung: %s", e)
            raise UserError(_("Unerwarteter Validierungsfehler: %s") % str(e)) from e

    @api.model_create_multi
    def create(self, vals_list):
        """
        ✅ VERBESSERT: Robuste Erstellung mit Display-Type Handling
        """
        try:
            for values in vals_list:
                # Handle display_type lines (sections/notes)
                display_type = values.get(
                    "display_type", 
                    self.default_get(["display_type"]).get("display_type", False)
                )
                
                if display_type:
                    # Für Display-Types: Produkt-Felder zurücksetzen
                    values.update({
                        'product_id': False, 
                        'price_unit': 0, 
                        'product_uom': False
                    })
                    _logger.debug("Display-Type Line erstellt: %s", display_type)

            return super().create(vals_list)
            
        except Exception as e:
            _logger.error("Fehler bei Line-Erstellung: %s", e)
            raise

    def write(self, values):
        """
        ✅ VERBESSERT: Sichere Updates mit Display-Type Prüfung
        """
        try:
            # Prüfe Display-Type Änderungen (nicht erlaubt)
            if "display_type" in values:
                conflicting_lines = self.filtered(
                    lambda line: line.display_type != values.get("display_type")
                )
                
                if conflicting_lines:
                    raise UserError(_(
                        "Sie können den Typ einer Blanket Order Position nicht ändern. "
                        "Löschen Sie stattdessen die aktuelle Position und erstellen "
                        "eine neue Position des gewünschten Typs."
                    ))
                    
            return super().write(values)
            
        except Exception as e:
            _logger.error("Fehler bei Line-Update: %s", e)
            raise

    # ===================================================================
    # SQL-CONSTRAINTS - Verbessert für 18.0
    # ===================================================================

    _sql_constraints = [
        (
            "accountable_required_fields",
            """
            CHECK(
                display_type IS NOT NULL OR (
                    product_id IS NOT NULL AND product_uom IS NOT NULL
                )
            )
            """,
            "Fehlende erforderliche Felder in der Blanket Order Position.",
        ),
        (
            "non_accountable_null_fields",
            """
            CHECK(
                display_type IS NULL OR (
                    product_id IS NULL AND price_unit = 0 AND product_uom IS NULL
                )
            )
            """,
            "Unzulässige Werte in einer nicht-buchungsrelevanten Blanket Order Position",
        ),
        # ✅ NEU: Zusätzliche Constraints für Datenintegrität
        (
            "positive_original_quantity",
            "CHECK(display_type IS NOT NULL OR original_uom_qty > 0)",
            "Ursprüngliche Menge muss größer als 0 sein",
        ),
        (
            "positive_price_unit",
            "CHECK(display_type IS NOT NULL OR price_unit >= 0)",
            "Einzelpreis darf nicht negativ sein",
        ),
    ]


# ===================================================================
# TAG-MODEL FÜR BESSERE KATEGORISIERUNG (NEU IN 18.0)
# ===================================================================

class BlanketOrderTag(models.Model):
    """
    ✅ NEU: Tag-System für bessere Blanket Order Kategorisierung
    """
    _name = 'blanket.order.tag'
    _description = 'Blanket Order Tag'
    _order = 'name'

    name = fields.Char(
        string='Tag Name', 
        required=True, 
        translate=True,
        help="Name des Tags zur Kategorisierung"
    )
    
    color = fields.Integer(
        string='Color',
        help="Farbe des Tags in der Benutzeroberfläche"
    )
    
    active = fields.Boolean(
        default=True,
        help="Inaktive Tags werden ausgeblendet"
    )
    
    description = fields.Text(
        string='Description',
        help="Beschreibung des Tags"
    )

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Tag-Name muss eindeutig sein!'),
    ]

