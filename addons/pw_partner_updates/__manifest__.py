# -*- coding: utf-8 -*-
{
    'name': "PW Partner Updates",

    'summary': "PW Partner Updates",

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

    'depends': ['base', 'sales_team', 'account','sale'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
