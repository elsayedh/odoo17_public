from odoo import fields, models, api, Command, _, registry
from odoo.addons.test_new_api.tests.test_new_fields import insert
from odoo.tools import groupby
import requests
from datetime import timedelta, datetime
import json
import logging
import calendar
from operator import attrgetter
from odoo.exceptions import ValidationError, UserError
from collections import defaultdict
import pandas as pd
from itertools import chain

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'order.pw.mixin']

    dup_orders = fields.Char(string='Duplicate Orders', search='_search_dup_orders', store=False)

    _sql_constraints = [('pw_id_unique', 'unique(pw_id,)', 'PW ID already exist.')]

    def _search_dup_orders(self, operator, value):
        if operator not in ('=', '!=', '<>'):
            raise UserError(_('Operation not supported'))

        query = """
                SELECT id
                FROM sale_order
                WHERE pw_id IN (
                    SELECT pw_id
                    FROM sale_order
                    GROUP BY pw_id
                    HAVING COUNT(*) > 1
                );
            """
        self.env.cr.execute(query)
        result = self.env.cr.fetchall()

        # Extract the order IDs and return them as ORM records
        order_ids = [row[0] for row in result]

        return [('id', 'in', order_ids)]

    def _prepare_confirmation_values(self):
        """ Prepare the sales order confirmation values.

        Note: self can contain multiple records.

        :return: Sales Order confirmation values
        :rtype: dict
        """

        # Override to stop changing the date order when confirm
        return {
            'state': 'sale',
            'date_order': fields.Datetime.now() if self.date_order == False else self.date_order
        }

    # Fetch B2B orders -------------------------------------------------------------------------------------------------
    @api.model
    def action_fetch_pw_b2b_orders(self, date=None, date_to=None, single_order=False):
        for company in self.env['res.company'].search([('pw_access_token', '!=', False)]):
            invoice_url = self.env['ir.config_parameter'].sudo().get_param('pw_invoice_info_all_endpoint')
            customer_invoices_of_period = dict()

            date_from = fields.Date.from_string(date) if date else fields.Date.today() - timedelta(days=1)
            date_to = fields.Date.from_string(date_to) if date_to else date_from

            while date_from <= date_to:

                fetch_date = date_from

                payload = "{\r\n  \"Date\": \"%s\"\r\n}" % str(fetch_date)

                headers = {
                    'Token': company.pw_access_token,
                    'Content-Type': 'text/plain'
                }

                json_data = []
                try:
                    self._action_log(_('Start fetch B2B Orders at date %s' % str(fetch_date)), log_type='info')

                    response = requests.request("POST", invoice_url, headers=headers, data=payload)

                    json_data = json.loads(response.text)

                    if 'message' in json_data and json_data['message']:
                        _logger.info(_('%s'), json_data['message'])

                    # Check if the returned data
                    if not isinstance(json_data, list) or len(json_data) == 0:
                        continue

                except Exception as e:
                    msg = 'Error while try fetch PW B2B orders at date %s : %s' % (fetch_date, e)
                    self._action_log(msg, log_type='error')
                    _logger.error(msg)

                for obj in json_data:
                    if single_order:
                        _logger.info(_('Fetching B2B Orders at date: %s'), fetch_date)
                        customer_invoices_of_period.update(obj.get('invoiceInfo', {}))

                    else:
                        for pw_order_id, order_data in obj.get('invoiceInfo', {}).items():
                            if order_data.get('Invoice'):
                                partner_id = self._get_partner(order_data.get('Customer'), company)
                                pw_user_id = order_data.get('Customer', {}).get('Rep_ID', False)
                                try:
                                    if self._get_order_by_pw_id(pw_order_id):
                                        # Continue if the order is existing
                                        continue

                                    order_id = self._get_order(pw_order_id, partner_id, pw_user_id, fetch_date, company)

                                    if order_id:
                                        order_id.order_line = self._get_order_lines(order_data.get('Products'))

                                        _logger.info(_('B2B Sale order %s (%s) was created from PW'), order_id.name,
                                                     pw_order_id)

                                        if 'errors' in self.env.context:
                                            error_mgs = '\n'.join(self.env.context.get('errors', []))
                                            self._action_log(error_mgs, log_type='warning', pw_order_id=pw_order_id,
                                                             order_id=order_id)

                                        # Order Confirm then generate invoice based on ordered qty
                                        order_id._sale_order_confirmation()

                                        # Commit changes
                                        self.env.cr.commit()

                                except Exception as e:
                                    msg = _('Error while create B2B sale order: %s' % e)
                                    order_json = {'pw_order_id': pw_order_id, 'partner_id': partner_id.id,
                                                  'pw_user_id': pw_user_id,
                                                  'fetch_date': fetch_date.strftime('%Y-%m-%d'),
                                                  'company': company.id, 'order': order_data, }
                                    self._action_log(msg, log_type='error', pw_order_id=pw_order_id,
                                                     order_json=json.dumps(order_json))
                                    _logger.error(msg)
                                    continue

                        self._action_log(_('Fetching B2B Orders at date %s successfully finished' % str(fetch_date)),
                                         log_type='info')

                date_from += timedelta(days=1)

            if single_order:
                self._create_b2b_sale_order_per_period(customer_invoices_of_period, date, date_to, company)

    # Fetch B2C orders -------------------------------------------------------------------------------------------------
    @api.model
    def action_fetch_pw_b2c_orders(self, date=None, date_to=None, single_order=False):
        for company in self.env['res.company'].search([('pw_access_token', '!=', False)]):
            date_from = fields.Date.from_string(date) if date else fields.Date.today() - timedelta(days=1)
            date_to = fields.Date.from_string(date_to) if date_to else date_from

            while date_from <= date_to:

                b2c_invoice_url = self.env['ir.config_parameter'].sudo().get_param('pw_invoice_b2c_by_date_endpoint')
                b2c_customer_id = self._get_partner({}, company, b2c=True)

                if not b2c_customer_id:
                    _logger.error(_('No B2C customer found!'))
                    break

                fetch_date = date_from

                payload = json.dumps({"Date": str(fetch_date)})
                headers = {'Token': company.pw_access_token, 'Content-Type': 'application/json'}

                try:
                    self._action_log(_('Start fetch B2C Orders at date %s' % str(fetch_date)), log_type='info')
                    response = requests.request("POST", b2c_invoice_url, headers=headers, data=payload)
                    json_data = json.loads(response.text)

                    if 'message' in json_data and json_data['message']:
                        _logger.info(_('%s'), json_data['message'])

                    if not isinstance(json_data, list) or len(json_data) == 0:
                        continue

                except Exception as e:
                    msg = 'Error while try fetch PW B2C orders at date %s : %s' % (fetch_date, e)
                    self._action_log(msg, log_type='error')
                    _logger.error(msg)
                    continue

                for obj in json_data:
                    if single_order:
                        order_id = self._create_b2c_sale_order_per_day(obj.get('orderList', []), fetch_date,
                                                                       b2c_customer_id, company)
                        if order_id:
                            order_id._sale_order_confirmation()
                    else:
                        for order in obj.get('orderList', []):
                            pw_order_id = order.get('order_id', 0)
                            pw_user_id = order.get('Rep_ID', 0)
                            order_id = False

                            if self._get_order_by_pw_id(pw_order_id):
                                continue

                            try:
                                order_id = self._get_order(pw_order_id, b2c_customer_id, pw_user_id, fetch_date,
                                                           company)

                                if order_id:
                                    order_id.order_line = self._get_order_lines(order, b2c=True)
                                    _logger.info(_('B2C Sale order %s (%s) was created from PW'), order_id.name,
                                                 pw_order_id)
                                    order_id._sale_order_confirmation()
                                    self.env.cr.commit()

                            except Exception as e:
                                msg = _('Error while create B2C sale order: %s' % e)
                                if order_id:
                                    order_id.sudo().unlink()
                                order_json = {'pw_order_id': pw_order_id, 'b2c_customer_id': b2c_customer_id.id,
                                              'pw_user_id': pw_user_id, 'fetch_date': fetch_date.strftime('%Y-%m-%d'),
                                              'company': company.id, 'order': order, 'b2c': True}
                                self._action_log(msg, log_type='error', pw_order_id=pw_order_id,
                                                 order_json=json.dumps(order_json))
                                _logger.error(msg)
                                continue

                self._action_log(
                    _('Fetching B2C Orders at date %s successfully finished' % str(fetch_date)), log_type='info')

            date_from += timedelta(days=1)

    # Get/Create Objs --------------------------------------------------------------------------------------------------
    def _get_partner(self, partner_data, company, b2c=False):
        if b2c:
            query = """
                    SELECT id
                    FROM res_partner
                    WHERE pw_b2c_customer = TRUE
                    AND (company_id = %s OR company_id IS NULL)
                    LIMIT 1;
                """
            self.env.cr.execute(query, (company.id,))
            result = self.env.cr.fetchone()  # Fetch one record (since we use LIMIT 1)

            partner_obj = self.env['res.partner']
            if result:
                partner_id = result[0]  # The ID of the partner is in the first column
                # Use browse() to return the ORM object
                return partner_obj.browse(partner_id)
            else:
                return partner_obj

        partner_vals = self._partner_vals_serializer(partner_data)
        partner_id = self._get_partner_by_pos_id(partner_vals['pw_pos_id'])
        if not partner_id:
            # partner_id = self.env['res.partner'].with_company(company.id).create(partner_vals)
            self.raise_error(_('Customer with POS No. "%s" not found, so "Unknown Customer" was created',
                               partner_data.get('pw_pos_id')))
            return self._create_unknown_customer(partner_vals['vat'], partner_vals['pw_pos_id'])
            # return self.env['res.partner'].search([('pw_b2b_default_customer', '=', True)], limit=1)

        return partner_id

    def _get_order(self, pw_order_id, partner_id, pw_user_id, date, company):
        order_id = self.env['sale.order'].with_company(company.id).create({
            'name': pw_order_id,
            'partner_id': partner_id.id,
            'date_order': date,
            'pw_id': pw_order_id,
            'user_id': self._get_user_by_pw_id(pw_user_id).id
        })

        return order_id

    def _get_order_lines(self, lines_vals, b2c=False):
        order_lines = list()
        if b2c:
            order_lines.append(Command.create(self._order_line_vals_serializer(lines_vals, b2c)))
            return order_lines

        for line in lines_vals:
            order_lines.append(Command.create(self._order_line_vals_serializer(line)))

        return order_lines

    def _get_product(self, product_data):
        product_vals = self._product_vals_serializer(product_data)
        product_id = self._get_product_by_pw_id(product_vals['pw_id'])
        if not product_id:
            # product_id = self.env['product.product'].create(product_vals)
            self.raise_error(_('Product with ID "%s" not found', product_vals['pw_id']))
            raise ValueError(_('Product with pw_id "%s" does not exit') % product_vals['pw_id'])
            # return self.env['product.product'].search([('pw_default_product', '=', True)], limit=1)

        return product_id

    # Search objs ------------------------------------------------------------------------------------------------------

    def _get_user_by_pw_id(self, pw_id):
        pw_id = pw_id.upper()  # Convert PW code to capital case
        return self.env['res.users'].search([('pw_id', '=', pw_id)], limit=1)

    def _get_order_by_pw_id(self, pw_id):
        if not pw_id:
            return False

        return self.env['sale.order'].search([('pw_id', '=', pw_id)], limit=1)

    def _get_product_by_pw_id(self, pw_id):
        if not pw_id:
            return False

        query = """
                SELECT pp.id
                FROM product_product pp
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                WHERE pt.pw_id = %s
                LIMIT 1;
            """
        # Execute the SQL query with pw_id as a parameter
        self.env.cr.execute(query, (pw_id,))

        # Fetch one record (since we use LIMIT 1)
        result = self.env.cr.fetchone()

        # If a result is found, convert the result into an ORM object
        product_obj = self.env['product.product']
        if result:
            product_id = result[0]  # The ID is the first column in the result
            # Use browse() to get the ORM object
            return product_obj.browse(product_id)
        else:
            return product_obj  # No matching record found

    # Objs Serialization -----------------------------------------------------------------------------------------------

    def _partner_vals_serializer(self, vals):
        partner_vals = dict()
        partner_vals['pw_pos_id'] = vals.get('POS_ID')
        partner_vals['name'] = vals.get('Name_AR')
        partner_vals['email'] = vals.get('Email')
        partner_vals['street'] = vals.get('Street_Address')
        partner_vals['city'] = vals.get('District')
        partner_vals['vat'] = vals.get('Vat_no')
        partner_vals['company_type'] = 'company'
        return partner_vals

    def _order_line_vals_serializer(self, vals, b2c=False):
        line_vals = dict()
        line_vals['product_id'] = self._get_product(vals).id
        line_vals['name'] = vals.get('Products')
        line_vals['product_uom_qty'] = float(vals.get('quantity')) if not b2c else float(vals.get('Quantity'))
        line_vals['price_unit'] = float(vals.get('price')) if not b2c else float(vals.get('Item_Price'))
        return line_vals

    def _product_vals_serializer(self, vals):
        product_vals = dict()
        product_vals['name'] = vals.get('Products')
        # product_vals['pw_brand'] = vals.get('Brand')
        product_vals['pw_id'] = vals.get('ProductsID')
        product_vals['invoice_policy'] = 'order'  # Create invoice based on ordered qty
        product_vals['detailed_type'] = 'product'
        product_vals['taxes_id'] = False
        return product_vals

    # MISC Function ----------------------------------------------------------------------------------------------------
    def _sale_order_confirmation(self, skip_check_invoicing_policy=False):
        # Filter to process only non-cancelled orders that are not in 'sale' or 'done' states and have order lines
        orders_to_process = self.filtered(lambda o: o.state not in ('sale', 'done', 'cancel') and o.order_line)

        # Confirm orders in bulk with context for immediate transfer
        try:
            for order in orders_to_process:
                order.with_context(default_immediate_transfer=True).action_confirm()
        except Exception as e:
            _logger.error(_('Error confirming orders: %s'), e)

        # Determine orders that need invoicing based on the invoicing policy
        if not skip_check_invoicing_policy:
            orders_to_invoiced = orders_to_process.filtered(
                lambda o: o.partner_id.pw_invoice_policy == 'ir' or o.partner_id.pw_b2c_customer
            )
        else:
            orders_to_invoiced = orders_to_process

        try:
            # Batch invoice creation
            orders_to_invoiced._create_invoices()

            # Group orders by date_order to set invoice and picking dates accordingly
            for date_order, grouped_orders in groupby(sorted(orders_to_invoiced, key=attrgetter('date_order')),
                                                      attrgetter('date_order')):
                grouped_orders = self.browse(
                    order.id for order in grouped_orders)  # Reconstruct recordset for batch write

                # Set invoice dates and post invoices in a batch
                unposted_invoices = grouped_orders.mapped('invoice_ids').filtered(
                    lambda inv: inv.state not in ('posted', 'cancel')
                )
                unposted_invoices.write({'invoice_date': date_order})
                unposted_invoices.action_post()

                # Update picking dates in batch for the grouped orders
                pickings_to_update = grouped_orders.mapped('picking_ids').filtered(lambda p: p.state != 'cancel')
                pickings_to_update.write({
                    'date_done': date_order,
                    'date_deadline': date_order,
                    'date': date_order,
                })

        except Exception as e:
            _logger.error(_('Error generating invoices or updating pickings: %s'), e)


    def raise_error(self, error_msg):
        ctx = dict(self.env.context)
        if 'errors' in ctx:
            ctx['errors'].append(error_msg)

        ctx['errors'] = [error_msg]

        self.env.context = ctx

    # Periodic Invoicing Orders ----------------------------------------------------------------------------------------
    @api.model
    def get_ready_order_ids(self, order_ids, date):
        result = self
        for order in order_ids:
            if order.date_order and order.date_order < date:
                result |= order
        return result

    @api.model
    def cron_auto_periodic_invoice(self):
        to_invoice_order_ids = self.search(
            [('invoice_status', '=', 'to invoice'), ('partner_id.pw_invoice_policy', 'in', ('kdr', 'ws'))])
        for partner, order_ids in groupby(to_invoice_order_ids, key=lambda o: o.partner_id):
            if partner.pw_invoice_frequency == 'week':
                today = datetime.now()
                date_to = today - timedelta(days=(today.weekday() + 1) % 7)
                date_from = date_to - timedelta(days=7)
                if date_from.month == date_to.month:
                    ready_order_ids = self.get_ready_order_ids(order_ids, date_to)
                    self._generate_invoice(ready_order_ids)
                else:
                    last_date_of_month = date_from.replace(day=calendar.monthrange(date_from.year, date_from.month)[1])
                    ready_order_ids = self.get_ready_order_ids(order_ids, last_date_of_month)
                    self._generate_invoice(ready_order_ids)
                    ready_order_ids = self.get_ready_order_ids(order_ids, date_to)
                    self._generate_invoice(ready_order_ids)
            else:
                ready_order_ids = self.get_ready_order_ids(order_ids,
                                                           self._get_date_ready_order(partner.pw_invoice_frequency))
                self._generate_invoice(ready_order_ids)

    def _generate_invoice(self, ready_order_ids):
        if ready_order_ids:
            sapi_wzd_id = self.env['sale.advance.payment.inv'].with_context(active_ids=ready_order_ids.ids).create({})
            invoice_ids = sapi_wzd_id._create_invoices(sapi_wzd_id.sale_order_ids)
            invoice_ids.action_post()

    def _get_date_ready_order(self, invoice_frequency):
        today = datetime.now().replace(hour=0, minute=0,
                                       second=0)

        if invoice_frequency == 'week':
            date = datetime.now() - timedelta(days=(today.weekday() + 1) % 7)  # First day in week is Sunday

        elif invoice_frequency == 'semi-month':
            if today.day <= 15:
                date = today.replace(day=1)

            else:
                date = today.replace(day=15)

        elif invoice_frequency == 'month':
            date = today.replace(day=1)

        elif invoice_frequency == 'quarter':
            if today.month in [1, 2, 3]:
                start_month = 1
            elif today.month in [4, 5, 6]:
                start_month = 4
            elif today.month in [7, 8, 9]:
                start_month = 7
            else:
                start_month = 10

            date = today.replace(month=start_month, day=1)

        elif invoice_frequency == 'semi-annual':
            if today.month <= 6:
                date = today.replace(month=1, day=1)

            else:
                date = today.replace(month=6, day=1)

        elif invoice_frequency == 'annual':
            date = today.replace(month=1, day=1)

        else:
            # Default value or in case invoice_frequency == 'day'
            date = today

        return date

    def action_split_order_invoices(self):
        to_invoice_order_ids = self.filtered(
            lambda o: o.invoice_status == 'to invoice' and o.partner_id.pw_invoice_policy in ('kdr', 'ws'))
        for partner, order_ids in groupby(to_invoice_order_ids, key=lambda o: o.partner_id):
            if partner.pw_invoice_frequency == 'day':
                self.prepare_daily_orders(order_ids)
            if partner.pw_invoice_frequency == 'week':
                self.prepare_weekly_orders(order_ids)
            if partner.pw_invoice_frequency == 'semi-month':
                self.prepare_semi_month_orders(order_ids)
            if partner.pw_invoice_frequency == 'month':
                self.prepare_monthly_orders(order_ids)
            if partner.pw_invoice_frequency == 'quarter':
                self.prepare_quarterly_orders(order_ids)
            if partner.pw_invoice_frequency == 'semi-annual':
                self.prepare_semi_annually_orders(order_ids)
            if partner.pw_invoice_frequency == 'annual':
                self.prepare_annually_orders(order_ids)

    @api.model
    def prepare_weekly_orders(self, order_ids):
        partner_orders = self.env['sale.order'].browse([order.id for order in order_ids])

        # Sort the orders by date
        partner_orders = partner_orders.sorted(key=attrgetter('date_order'))

        def get_week_start(date):
            # Calculate the start of the week (Saturday)
            weekday = date.weekday()
            # If the day is not Saturday, move back to the last Saturday
            delta_days = (weekday + 1) % 7
            return date - timedelta(days=delta_days)

        def get_week_number(order):
            date = order.date_order
            # Find the start of the week
            week_start = get_week_start(date)
            # Get the ISO calendar details from the week start date
            iso_year, iso_week, iso_weekday = week_start.isocalendar()
            return iso_week

        # Group partner's orders by year, month, and week (Saturday to Saturday)
        for year, year_orders in groupby(partner_orders, key=lambda order: order.date_order.year):
            for month, month_orders in groupby(year_orders, key=lambda order: order.date_order.month):
                for week_number, week_orders in groupby(month_orders, key=get_week_number):
                    # Convert orders to a recordset
                    orders = self.env['sale.order'].browse([order.id for order in week_orders])
                    self._generate_invoice(orders)

    def prepare_semi_month_orders(self, order_ids):
        partner_orders = self.env['sale.order'].browse([order.id for order in order_ids])

        # Sort the orders by date
        partner_orders = partner_orders.sorted(key=attrgetter('date_order'))

        def get_semi_month(order):
            # Determine the semi-month based on the day of the month
            if order.date_order.day <= 15:
                return 'first'
            else:
                return 'second'

        # Group partner's orders by year, month, and week (Saturday to Saturday)
        for year, year_orders in groupby(partner_orders, key=lambda order: order.date_order.year):
            for month, month_orders in groupby(year_orders, key=lambda order: order.date_order.month):
                for semi_month, week_orders in groupby(month_orders, key=get_semi_month):
                    # Convert orders to a recordset
                    orders = self.env['sale.order'].browse([order.id for order in week_orders])
                    self._generate_invoice(orders)

    def prepare_monthly_orders(self, order_ids):
        partner_orders = self.env['sale.order'].browse([order.id for order in order_ids])

        # Sort the orders by date
        partner_orders = partner_orders.sorted(key=attrgetter('date_order'))

        def get_semi_month(order):
            # Determine the semi-month based on the day of the month
            if order.date_order.day <= 15:
                return 'first'
            else:
                return 'second'

        # Group partner's orders by year, month, and week (Saturday to Saturday)
        for year, year_orders in groupby(partner_orders, key=lambda order: order.date_order.year):
            for month, month_orders in groupby(year_orders, key=lambda order: order.date_order.month):
                # Convert orders to a recordset
                orders = self.env['sale.order'].browse([order.id for order in month_orders])
                self._generate_invoice(orders)

    def prepare_annually_orders(self, order_ids):
        partner_orders = self.env['sale.order'].browse([order.id for order in order_ids])

        # Sort the orders by date
        partner_orders = partner_orders.sorted(key=attrgetter('date_order'))

        # Group partner's orders by year, month, and week (Saturday to Saturday)
        for year, year_orders in groupby(partner_orders, key=lambda order: order.date_order.year):
            # Convert orders to a recordset
            orders = self.env['sale.order'].browse([order.id for order in year_orders])
            self._generate_invoice(orders)

    def prepare_quarterly_orders(self, order_ids):
        partner_orders = self.env['sale.order'].browse([order.id for order in order_ids])

        # Sort the orders by date
        partner_orders = partner_orders.sorted(key=attrgetter('date_order'))

        # Group partner's orders by year, month, and week (Saturday to Saturday)
        for year, year_orders in groupby(partner_orders, key=lambda order: order.date_order.year):
            for month, month_orders in groupby(year_orders, key=lambda order: (order.date_order.month - 1) // 3 + 1):
                # Convert orders to a recordset
                orders = self.env['sale.order'].browse([order.id for order in month_orders])
                self._generate_invoice(orders)

    def prepare_semi_annually_orders(self, order_ids):
        partner_orders = self.env['sale.order'].browse([order.id for order in order_ids])

        # Sort the orders by date
        partner_orders = partner_orders.sorted(key=attrgetter('date_order'))

        # Group partner's orders by year, month, and week (Saturday to Saturday)
        for year, year_orders in groupby(partner_orders, key=lambda order: order.date_order.year):
            for month, month_orders in groupby(year_orders, key=lambda order: 1 if order.date_order.month <= 6 else 2):
                # Convert orders to a recordset
                orders = self.env['sale.order'].browse([order.id for order in month_orders])
                self._generate_invoice(orders)

    @api.model
    def prepare_daily_orders(self, order_ids):
        partner_orders = self.env['sale.order'].browse([order.id for order in order_ids])

        # Group partner's orders by date
        for order_date, orders in groupby(partner_orders.sorted(key=attrgetter('date_order')),
                                          key=lambda o: o.date_order.date()):
            # Convert orders to a recordset
            orders = self.env['sale.order'].browse([order.id for order in orders])
            self._generate_invoice(orders)

    # Single B2C Order per Day -----------------------------------------------------------------------------------------

    def _create_b2c_sale_order_per_day(self, lines, date, b2c_customer_id, company):

        # Check if order in same date is existing
        query = """
            SELECT sale.id
            FROM sale_order sale
            JOIN res_partner customer ON sale.partner_id = customer.id
            WHERE customer.pw_b2c_customer = TRUE 
            AND sale.date_order::date = %s
            AND sale.state != 'cancel'
        """

        self.env.cr.execute(query, (date,))
        result = self.env.cr.fetchall()

        if result:
            _logger.error(_('B2C order with same date: %s already exists'), date)
            return False

        order_id = self.create({
            'date_order': date,
            'partner_id': b2c_customer_id.id,
            'company_id': company.id,
        })

        lines_by_product = self._group_lines_by_product(lines)
        self._insert_b2c_sale_order_lines(lines_by_product, order_id)

        # Recompute totals
        order_id.order_line._compute_tax_id()
        order_id.order_line._compute_amount()

        _logger.info(_('B2C order with date: %s successfully created.'), date)
        return order_id

    def _group_lines_by_product(self, lines):
        """
            Group the given lines by ProductsID and calculate total quantity and item price for each product.

            :param lines: List of dictionaries representing line items
            :type lines: list

            :return: List of dictionaries with product_id, total_quantity, and item_price for each product
            :rtype: list
        """
        # Sort the lines by ProductsID to ensure groupby works correctly
        sorted_lines = sorted(lines, key=lambda x: x['ProductsID'])
        # Group the lines by ProductsID
        grouped_lines = groupby(sorted_lines, key=lambda x: x['ProductsID'])
        # Convert the grouped lines to a dictionary
        grouped_dict = {key: list(group) for key, group in grouped_lines}

        lines_by_product = []
        for product_id, orders in grouped_dict.items():
            total_quantity = sum(int(order['Quantity']) for order in orders)
            item_price = float(orders[0]['Item_Price']) if orders else 0.0
            lines_by_product.append(
                {'product_id': product_id, 'total_quantity': total_quantity, 'item_price': item_price})

        return lines_by_product

    def _insert_b2c_sale_order_lines(self, lines, order_id):
        """
            Insert sale order lines into the database in bulk.

            :param lines: List of dictionaries containing line items data
            :type lines: list
            :param order_id: Sale order ID
            :type order_id: int

            :return: True if insertion is successful
            :rtype: bool
        """

        if not lines:
            return

        # Prepare the base SQL query
        query = """
                    INSERT INTO sale_order_line (product_id, product_uom_qty, price_unit, name, order_id, customer_lead, product_uom, company_id)
                    SELECT p.id, %s, %s, pt.name->>'en_US', %s, 0.0, pt.uom_id, %s
                    FROM product_product p
                    JOIN product_template pt ON pt.id = p.product_tmpl_id
                    WHERE pt.pw_id = %s OR pt.pw_default_product = True
        """

        # Create a list of values to be inserted
        values = [(item['total_quantity'], item['item_price'], order_id.id, order_id.company_id.id, item['product_id'])
                  for item in lines]

        # Use a transaction to commit in bulk
        try:
            # Execute the query using batch inserts
            self.env.cr.executemany(query, values)

            # Commit the transaction to save the changes
            self.env.cr.commit()

        except Exception as e:
            # Rollback in case of an error
            self.env.cr.rollback()
            _logger.error("Error inserting sale order lines: %s", e)

        return True

    # Single B2B order per period -----------------------------------------------------------------------------------------

    def _create_b2b_sale_order_per_period(self, invoices, date, date_to, company):
        # Remove first obj that it is not an invoice
        if "0" in invoices:
            invoices.pop("0")

        grouped_invoices = self._group_invoices_by_customer(invoices)
        order_ids = self.env['sale.order']
        for invoice in grouped_invoices:
            partner_id = self._get_partner_by_pos_id(invoice['pos_id'])
            if not partner_id:
                _logger.error(_('No customer with POS ID: %s found!'), invoice['pos_id'])
                partner_id = self._create_unknown_customer(vat='000', pos=invoice['pos_id'])

            # Check if order in same date is existing
            query = """
                    SELECT sale.id
                    FROM sale_order sale
                    JOIN res_partner customer ON sale.partner_id = customer.id
                    WHERE customer.pw_pos_id = %s 
                    AND sale.date_order::date BETWEEN %s AND %s
                    AND sale.state != 'cancel'
                """

            self.env.cr.execute(query, (invoice['pos_id'], date, date_to,))
            result = self.env.cr.fetchall()

            if result:
                _logger.error(_('B2B order with same date: %s for customer (POS ID): %s already exists'), date,
                              invoice['pos_id'])
                continue

            order_id = self.create({
                'date_order': date_to,
                'partner_id': partner_id.id,
                'company_id': company.id,
            })
            invoice['invoice_lines'] = list(map(lambda item: {**item, "order_id": order_id}, invoice['invoice_lines']))
            order_ids |= order_id

        # Insert SOL in created sales orders
        self._insert_b2b_sale_order_lines(list(chain(*list(map(lambda i: i['invoice_lines'], grouped_invoices)))))

        # Recompute totals
        self.env.add_to_compute(order_ids.order_line._fields['tax_id'], order_ids.order_line)
        self.env.add_to_compute(order_ids.order_line._fields['price_subtotal'], order_ids.order_line)
        self.env.add_to_compute(order_ids.order_line._fields['price_tax'], order_ids.order_line)
        self.env.add_to_compute(order_ids.order_line._fields['price_total'], order_ids.order_line)

        self.env.add_to_compute(order_ids._fields['amount_untaxed'], order_ids)
        self.env.add_to_compute(order_ids._fields['amount_tax'], order_ids)
        self.env.add_to_compute(order_ids._fields['amount_total'], order_ids)

        order_ids._sale_order_confirmation(skip_check_invoicing_policy=True)

        _logger.info(_('B2B orders with date: %s To date: %s successfully created.'), date, date_to)

        return True

    def _insert_b2b_sale_order_lines(self, invoice_lines):
        query = """
                INSERT INTO sale_order_line (product_id, product_uom_qty, price_unit, name, order_id, customer_lead, product_uom, company_id)
                SELECT p.id, %s, %s, pt.name->>'en_US', %s, 0.0, pt.uom_id, %s
                FROM product_product p
                JOIN product_template pt ON pt.id = p.product_tmpl_id
                WHERE pt.pw_id = %s OR pt.pw_default_product = True
        """

        # Create a list of values to be inserted
        values = [
            (item['quantity'], item['price'], item['order_id'].id, item['order_id'].company_id.id, item['ProductsID'])
            for item in invoice_lines]

        # Use a transaction to commit in bulk
        try:
            # Execute the query using batch inserts
            self.env.cr.executemany(query, values)

            # Commit the transaction to save the changes
            self.env.cr.commit()

        except Exception as e:
            # Rollback in case of an error
            self.env.cr.rollback()
            _logger.error("Error inserting sale order lines: %s", e)

        return True

    def _group_invoices_by_customer(self, invoices):
        # Initialize an empty list to store the flattened data
        flattened_data = []

        # Flatten the data by POS_ID and ProductsID
        for invoice_id, invoice_data in invoices.items():
            pos_id = invoice_data['Customer']['POS_ID']
            for product in invoice_data['Products']:
                product_data = {
                    "POS_ID": pos_id,
                    "ProductsID": product["ProductsID"],
                    "quantity": int(product["quantity"]),
                    "price": float(product["price"])
                }
                flattened_data.append(product_data)

        # Convert the flattened data into a DataFrame
        df = pd.DataFrame(flattened_data)

        # Group by POS_ID and ProductsID, sum the quantities, and keep the price (since it's the same for each product)
        grouped_df = df.groupby(['POS_ID', 'ProductsID']).agg({
            'quantity': 'sum',
            'price': 'first'  # Take the first price as they are the same for identical products
        }).reset_index()

        # Convert the grouped DataFrame into the desired format (POS_ID and invoice_lines)
        grouped_customer_invoices = []
        for pos_id, pos_data in grouped_df.groupby('POS_ID'):
            invoice_lines = pos_data[['ProductsID', 'quantity', 'price']].to_dict(orient='records')
            grouped_customer_invoices.append({
                'pos_id': pos_id,
                'invoice_lines': invoice_lines
            })

        return grouped_customer_invoices

    # Server Actions ---------------------------------------------------------------------------------------------------

    def action_cancel_duplicated_orders(self):
        for order in self:
            if order.state != 'cancel':
                ids = self.ids
                ids.remove(order.id)
                other_order_ids = self.env['sale.order'].search(
                    [('id', 'in', ids), ('state', '!=', 'cancel'), ('pw_id', '=', order.pw_id)])
                for other_order in other_order_ids:
                    other_order_ids.invoice_ids.filtered(lambda i: i.state == 'posted').button_draft()
                    other_order._action_cancel()
                    # cancel Pickings
                    for picking in other_order.picking_ids:
                        if picking.state == 'done':
                            stock_return_picking = self.env['stock.return.picking'].with_context(
                                active_ids=other_order.picking_ids.ids, active_id=other_order.picking_ids.ids[0],
                                active_model='stock.picking').create({})
                            # stock_return_picking.product_return_moves.quantity = 1.0
                            stock_return_picking_action = stock_return_picking.create_returns()
                            return_picking = self.env['stock.picking'].browse(stock_return_picking_action['res_id'])
                            return_picking.move_ids.picked = True
                            return_picking.button_validate()
                        else:
                            picking.action_cancel()
                    # for invoice in other_order.invoice_ids:
                    #     if invoice.state == 'posted':
                    # reversal_wizard = self.env['account.move.reversal'] \
                    #     .with_context(active_model='account.move', active_ids=invoice.ids) \
                    #     .create({'reason': "Duplicated", 'journal_id': invoice.journal_id.id})
                    # refund = self.env['account.move'].browse(reversal_wizard.refund_moves()['res_id'])
                    # refund.action_post()
                    # else:

    def _sale_deliver_order(self):
        if self.state == 'cancel':
            return
        try:
            if self.state not in ('sale', 'done'):
                self.with_context(default_immediate_transfer=True).action_confirm()
            try:
                for picking_id in self.picking_ids:
                    # for line in picking_id.move_ids_without_package:
                    #     line.quantity = line.product_uom_qty
                    if picking_id.state != 'done':
                        picking_id.action_confirm()
                        picking_id.button_validate()

                    msg = _('Picking of order %s was validated' % self.pw_id)
                    self._action_log(msg, log_type='info', pw_order_id=self.pw_id)
                    _logger.info(msg)

            except Exception as e:
                msg = _('Order Picking Not Validated or already validated: %s' % e)
                self._action_log(msg, log_type='error', pw_order_id=self.pw_id, )
                _logger.error(msg)

        except Exception as e:
            msg = _('Order Picking Not Validated or already validated: %s' % e)
            self._action_log(msg, log_type='error', pw_order_id=self.pw_id, )
            _logger.error(msg)

    @api.model
    def action_deliver_order(self, date=False, date_to=False):
        if not date:
            date = fields.Date.today() - timedelta(days=1)
        else:
            date = fields.Date.from_string(date)
        if not date_to:
            date_to = date
        else:
            date_to = fields.Date.from_string(date_to)
        order_ids = self.search([('date_order', '>=', date), ('date_order', '<=', date_to)])
        for sale in order_ids:
            self._sale_deliver_order(sale, sale.date_order)

    @api.model
    def cron_fetch_b2b_orders(self, date=None, date_to=None):
        self.fetch_orders(
            order_type='B2B',
            date=date,
            date_to=date_to,
            json_payload=True,
            transaction_list_name='invoiceInfo',
            endpoint_param_key='pw_invoice_info_all_endpoint'
        )
