from odoo import fields, models, api


class Partner(models.Model):
    _inherit = 'res.partner'

    pw_pos_id = fields.Char(string='POS ID')
    pw_b2c_customer = fields.Boolean(string='B2C Customer')
    pw_b2b_default_customer = fields.Boolean(string='B2B Default Customer')
    pw_invoice_policy = fields.Selection([('ir', 'IR'), ('kdr', 'KDR'), ('ws', 'WS')], default='ir',
                                         string='Invoicing Policy')
    pw_invoice_frequency = fields.Selection(
        [('day', 'Daily'),
         ('week', 'Weekly'),
         ('semi-month', 'Semi-Monthly'),
         ('month', 'Monthly'),
         ('quarter', 'Quarterly'),
         ('semi-annual', 'Semi-Annual'),
         ('annual', 'Annually')], string='Invoicing Frequency', default='day')

    customer_representative_contact = fields.Boolean(string='Customer Representative Contact')

    _sql_constraints = [('pw_id_unique', 'unique(pw_pos_id,)', 'pw_pos_id already exist.')]

    @api.onchange('pw_invoice_policy')
    def _onchange_pw_invoice_policy(self):
        if self.pw_invoice_policy == 'ir':
            self.pw_invoice_frequency = 'day'

    @api.onchange('company_type')
    def _onchange_company_type(self):
        if self.company_type == 'person':
            self.pw_invoice_frequency = 'day'
