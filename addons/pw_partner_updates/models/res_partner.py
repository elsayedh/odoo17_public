from odoo import fields, models, api


class Partner(models.Model):
    _inherit = 'res.partner'

    old_code = fields.Char(string='Portal Delta Code')
    account_code = fields.Char(string='Account ID')
    region_id = fields.Many2one('partner.region', string='Region ')
    type_id = fields.Many2one('partner.type', string='Partner Type ')
    class_id = fields.Many2one('partner.class', string='Partner Class ')
    cr_id = fields.Char(string='CR ID')



class PartnerClass(models.Model):
    _name = 'partner.class'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(String="Code")


class PartnerType(models.Model):
    _name = 'partner.type'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(String="Code")


class PartnerRegion(models.Model):
    _name = 'partner.region'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(String="Code")
