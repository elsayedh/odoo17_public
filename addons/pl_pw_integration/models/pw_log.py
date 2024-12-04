from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import logging
import json

_logger = logging.getLogger(__name__)


class PWLog(models.Model):
    _name = 'pw.log'
    _description = 'PW Log'
    _order = 'date desc'

    name = fields.Char('Description', required=True)
    date = fields.Datetime('Date', required=True)
    sale_id = fields.Many2one('sale.order', string='Sale Order')
    pw_id = fields.Char(string='PW ID')
    log_type = fields.Selection([('info', 'INFO'), ('warning', 'WARNING'), ('error', 'ERROR')], string='Log Type',
                                required=True)
    solved = fields.Boolean('Solved')
    order_json = fields.Json('Order JSON', )
    is_picking = fields.Boolean()

    def create_b2c_order(self, sale_order, order_json):
        order_json = json.loads(order_json)
        pw_order_id = order_json['pw_order_id']
        b2c_customer_id = self.env['res.partner'].browse(order_json['b2c_customer_id'])
        pw_user_id = order_json['pw_user_id']
        fetch_date = order_json['fetch_date']
        company = self.env['res.company'].browse(order_json['company'])
        order_id = sale_order._get_order(pw_order_id, b2c_customer_id, pw_user_id, fetch_date, company)

        if order_id:
            order_id.order_line = sale_order._get_order_lines(order_json['order'], b2c=True)

            _logger.info(_('B2C Sale order %s (%s) was created from PW'), order_id.name,
                         pw_order_id)

            # Order Confirm the generate invoice based on ordered qty
            if order_id.state not in ('sale', 'done'):
                order_id.with_context(default_immediate_transfer=True).action_confirm()
                for picking_id in order_id.picking_ids:
                    for line in picking_id.move_ids_without_package:
                        line.quantity = line.product_uom_qty
                    picking_id.button_validate()
                order_id._create_invoices()
                for invoice in order_id.invoice_ids:
                    invoice.invoice_date = fetch_date
                    invoice.action_post()

    def create_b2b_order(self, sale_order, order_json):
        order_json = json.loads(order_json)
        pw_order_id = order_json['pw_order_id']
        partner_id = self.env['res.partner'].browse(order_json['partner_id'])
        pw_user_id = order_json['pw_user_id']
        fetch_date = order_json['fetch_date']
        company = self.env['res.company'].browse(order_json['company'])
        order_id = sale_order._get_order(pw_order_id, partner_id, pw_user_id, fetch_date, company)

        if order_id:
            order_id.order_line = sale_order._get_order_lines(order_json['order'], )

            _logger.info(_('B2C Sale order %s (%s) was created from PW'), order_id.name,
                         pw_order_id)

            # Order Confirm the generate invoice based on ordered qty
            if order_id.state not in ('sale', 'done'):
                order_id.with_context(default_immediate_transfer=True).action_confirm()
                for picking_id in order_id.picking_ids:
                    for line in picking_id.move_ids_without_package:
                        line.quantity = line.product_uom_qty
                    picking_id.button_validate()
                order_id._create_invoices()
                for invoice in order_id.invoice_ids:
                    invoice.invoice_date = fetch_date
                    invoice.action_post()

    def create_stock_picking(self, order_json):
        order_json = json.loads(order_json)
        pw_order_id = order_json.get('orderID', 0)
        try:
            picking_id = self.env['stock.picking'].sudo()._get_order(order_json, self.env.company)
            picking_id.move_ids_without_package = self.env['stock.picking'].sudo()._get_order_line(order_json,
                                                                                                   self.env.company)
            picking_id.action_confirm()
            picking_id.button_validate()
            _logger.info(_('Stock order %s (%s) was created from PW'), picking_id.name, pw_order_id)

            self.env.cr.commit()

        except Exception as e:
            msg = _('Error while create picking: %s' % e)
            _logger.error(msg)

    def action_create_order(self):
        self = self.sudo()
        for rec in self:
            if not rec.solved:
                sale_order = self.env['sale.order']
                if rec.order_json:
                    order_json = rec.order_json
                    if 'PO_Reference' in order_json:
                        self.create_stock_picking(order_json)

                    elif 'b2c' in order_json:
                        self.create_b2c_order(sale_order, order_json)

                    else:
                        self.create_b2b_order(sale_order, order_json)

                    rec.action_solved()

    def action_solved(self):
        self.sudo().solved = True

    def action_open_order(self):
        if not self.sale_id:
            raise ValidationError(_("No sale order to be open"))

        return {
            'name': _('Sale Order'),
            'view_mode': 'form',
            'res_model': 'sale.order',
            'res_id': self.sale_id.id,
            'type': 'ir.actions.act_window',
        }
