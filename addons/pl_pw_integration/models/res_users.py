from odoo import fields, models, api


class User(models.Model):
    _inherit = 'res.users'

    pw_id = fields.Char(string='PW ID')
    


    _sql_constraints = [('pw_id_unique', 'unique(pw_id,)', 'pw_id already exist.')]
