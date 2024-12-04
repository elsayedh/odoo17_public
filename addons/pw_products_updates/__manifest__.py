# -*- coding: utf-8 -*-
{
    'name': "PW Product Updates",

    'summary': "PW Product Updates",

    'description': """
        PW Product Updates
    """,

    'author': "Plementus",
    'website': "https://www.plementus.com",
    'contributors': [
        'm.roshdy@plementus.com',
    ],

    'category': 'product',
    'version': '0.1',

    'depends': ['base', 'product', 'stock'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
