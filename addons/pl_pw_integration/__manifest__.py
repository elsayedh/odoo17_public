# -*- coding: utf-8 -*-
{
    'name': "PW Integration",

    'summary': "PW Integration",

    'description': """
PW Integration
    """,

    'author': "Plementus",
    'website': "https://www.plementus.com",
    'contributors': [
        'm.roshdy@plementus.com',
    ],

    'category': 'sale',
    'version': '0.1',

    'depends': ['base', 'sale', 'stock', 'account', 'pw_products_updates', 'pw_partner_updates'],

    # always loaded
    'data': [
        'data/data.xml',
        'data/server_actions.xml',
        'data/token.xml',
        'data/ir_cron.xml',
        'security/ir.model.access.csv',
        'views/res_company_view.xml',
        'views/res_partner_view.xml',
        'views/pw_log_view.xml',
        'views/product_template_views.xml',
        'views/res_config_settings_view.xml',
        'views/sale_order_view.xml',
        'views/account_account_view.xml',
        'views/res_users_view.xml',
    ],

}
