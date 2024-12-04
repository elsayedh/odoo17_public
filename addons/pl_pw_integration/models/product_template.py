from odoo import fields, models, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    pw_id = fields.Char(string='PW ID')
    pw_default_product = fields.Boolean(string='PW Default Product')

    _sql_constraints = [('pw_id_unique', 'unique(pw_id,)', 'PW ID already exist.')]
