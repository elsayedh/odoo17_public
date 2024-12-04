from odoo import fields, models, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    family_id = fields.Many2one('product.family', 'Family', ondelete='cascade')
    brand_id = fields.Many2one('product.brand', 'Brand', ondelete='cascade')
    model_id = fields.Many2one('product.model', 'Model', ondelete='cascade')
    is_digital_product = fields.Boolean(string="Is Digital EVD")
    delta_code = fields.Char(string="Delta Code")
    item_code = fields.Char(string="Item Code")


class ProductModel(models.Model):
    _name = 'product.model'

    name = fields.Char('Name', required=True, translate=True)


class ProductFamily(models.Model):
    _name = 'product.family'

    name = fields.Char('Name', required=True, translate=True)


class ProductBrand(models.Model):
    _name = 'product.brand'

    name = fields.Char('Name', required=True, translate=True)
