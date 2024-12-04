from odoo import fields, models, api


class Account(models.Model):
    _inherit = 'account.account'

    pw_account_number = fields.Char(string='PW Account Number')

    @api.model
    def get_pw_account(self, account_number):
        return self.sudo().search([('pw_account_number', '=', account_number)], limit=1)
