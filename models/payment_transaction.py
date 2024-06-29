import logging
import pprint
from datetime import datetime, timedelta

from odoo import models, fields, api, _
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.models.payment_provider import ValidationError
from odoo.exceptions import UserError
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)
import base64, requests

try:
    from .. import conekta
except (ImportError, IOError) as err:
    _logger.debug(err)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    conekta_oxxo_reference = fields.Char("Oxxo/SPEI Payment Reference")
    conekta_oxxo_barcode = fields.Binary(string='Oxxo Barcode')
    conekta_oxxo_expire_date = fields.Date(string="Oxxo expire date")
    conekta_spei_receiving_account_number = fields.Char("SPEI Receiving account number")
    conekta_spei_receiving_account_bank = fields.Char("SPEI Receiving account bank")

    def create_params(self, provider):
        params = {}
        partner = self.partner_id
        if not hasattr(self, 'sale_order_ids') and not hasattr(self, 'invoice_ids'):
            raise Warning("Can't create payment without Sale order or Invoice in conekta.")
        if hasattr(self, 'sale_order_ids') and not self.sale_order_ids and hasattr(self,
                                                                                   'invoice_ids') and not self.invoice_ids:
            raise Warning("Can't create payment without Sale order or Invoice in conekta.")

        if self.sale_order_ids:
            partner = self.sale_order_ids[0].partner_id
        if self.invoice_ids:
            partner = self.invoice_ids[0].partner_id

        # params['description'] = _('%s Order %s' % (company_name, self.reference))
        params['amount'] = int(self.amount)
        if self.currency_id.name not in ['MXN', 'USD']:
            raise Warning("Only MXN and USD currency supported.")

        params['currency'] = self.currency_id.name
        params['metadata'] = {"reference": self.reference}
        params['reference_id'] = self.reference

        if provider == 'conekta':
            if 'src' in self.token_id.conekta_token:
                params['charges'] = [{
                    "payment_method": {
                        "type": "card",
                        "payment_source_id": self.token_id and self.token_id.conekta_token or None
                    }
                }]
            else:
                params['charges'] = [{
                    "payment_method": {
                        "type": "card",
                        "token_id": self.token_id and self.token_id.conekta_token or None
                    }
                }]
        elif provider == 'conekta_oxxo':
            params['charges'] = [{
                "payment_method": {
                    "type": "oxxo_cash",
                }
            }]
        elif provider == 'conekta_spei':
            thirty_days_from_now = int((datetime.now() + timedelta(days=1)).timestamp())
            params['charges'] = [{
                "payment_method": {
                    "type": "spei",
                    "expires_at": thirty_days_from_now
                }
            }]

            # params['charges'] = {'type': 'oxxo'}
            # TODO: ADD expires_at
        partner_name = partner.name or self.partner_name or ''
        partner_email = partner.email or self.partner_email or ''

        if self.partner_id.conekta_client_id:
            params['customer_info'] = {
                'customer_id': self.partner_id.conekta_client_id
            }
        else:
            details = params['customer_info'] = {}
            details['name'] = partner_name.replace('_', ' ')
            details['phone'] = partner.phone or partner.mobile or ''
            details['email'] = email_normalize(partner_email,False)

        line_items = params['line_items'] = []
        discount_lines = params['discount_lines'] = []
        tax_lines = {}
        is_subscription = False
        if hasattr(self, 'sale_order_ids'):
            total_amount = 0
            total_amount_untaxed = 0
            for order in self.sale_order_ids:
                is_subscription = True if order.is_subscription else False
                total_amount += order.amount_total
                total_amount_untaxed += order.amount_untaxed
                for line in order.order_line:
                    _logger.info(f"line: {line}")
                    price_reduce = line.price_unit * (1.0 - line.discount / 100.0)
                    if line.tax_id:
                        res = line.tax_id.compute_all(price_reduce, quantity=line.product_uom_qty,
                                                      product=line.product_id, partner=order.partner_shipping_id)
                        taxes = res['taxes']
                        price_unit = res.get('total_excluded') / line.product_uom_qty
                        for tax in taxes:
                            if (tax['id'], tax['name']) not in tax_lines:
                                tax_lines[(tax['id'], tax['name'])] = tax['amount']
                            else:
                                tax_lines[(tax['id'], tax['name'])] = tax_lines[(tax['id'], tax['name'])] + tax[
                                    'amount']
                    else:
                        price_unit = price_reduce
                    if price_unit < 0:
                        d_item = {}
                        discount_lines.append(d_item)
                        d_item['code'] = 'Cupón de descuento'
                        d_item['type'] = 'coupon'
                        d_item['amount'] = abs(int(price_unit * 100)) or 1
                    else:
                        item = {}
                        line_items.append(item)
                        item['name'] = line.product_id.name or ''
                        item['description'] = line.product_id.description_sale or line.product_id.name or ''
                        item['unit_price'] = int(price_unit * 100) or 1
                        item['quantity'] = int(line.product_uom_qty) or 1
                        # item['sku'] = line.product_id.default_code or ''
                        item['category'] = line.product_id.categ_id.name or ''
                        if line.product_id.default_code:
                            item['sku'] = line.product_id.default_code or ''
            # If price include taxes, than Amount need to pass untaxed amount
            if self.amount == total_amount and tax_lines:
                params['amount'] = int(total_amount_untaxed)
        if hasattr(self, 'invoice_ids') and not is_subscription:
            total_amount_invoice = 0
            total_amount_untaxed_invoice = 0

            for invoice in self.invoice_ids:
                _logger.info(f"Invoice: {invoice}")
                total_amount_invoice += invoice.amount_total
                total_amount_untaxed_invoice += invoice.amount_untaxed
                for line in invoice.invoice_line_ids:
                    if (line.price_subtotal / line.quantity) < 0:
                        d_item = {}
                        discount_lines.append(d_item)
                        d_item['code'] = 'Cupón de descuento'
                        d_item['type'] = 'coupon'
                        d_item['amount'] = abs(int((line.price_subtotal / line.quantity) * 100)) or 1
                    else:
                        item = {}
                        line_items.append(item)
                        item['name'] = line.product_id.name or ''
                        item['description'] = line.product_id.description_sale or line.product_id.name or ''
                        item['unit_price'] = int((line.price_subtotal / line.quantity) * 100) or 1
                        item['quantity'] = int(line.quantity) or 1
                        item['category'] = line.product_id.categ_id.name or ''
                        if line.product_id.default_code:
                            item['sku'] = line.product_id.default_code or ''
                    if line.tax_ids:
                        line_discount_price_unit = line.price_unit * (1 - (line.discount / 100.0))
                        taxes_res = line.tax_ids.compute_all(
                            line_discount_price_unit,
                            quantity=line.quantity,
                            currency=line.currency_id,
                            product=line.product_id,
                            partner=line.partner_id,
                            is_refund=line.is_refund,
                        )
                        taxes = taxes_res['taxes']
                        for tax in taxes:
                            if (tax['id'], tax['name']) not in tax_lines:
                                tax_lines[(tax['id'], tax['name'])] = tax['amount']
                            else:
                                tax_lines[(tax['id'], tax['name'])] = tax_lines[(tax['id'], tax['name'])] + tax['amount']

            # If price include taxes, than Amount need to pass untaxed amount
            if self.amount == total_amount_invoice and tax_lines:
                params['amount'] = int(total_amount_untaxed_invoice)
        if tax_lines:
            tax_lines_conekta = params['tax_lines'] = []
            for tax_name, amount in tax_lines.items():
                item = {'description': tax_name[1], 'amount': int(amount * 100)}
                tax_lines_conekta.append(item)
        return params

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code not in ['conekta', 'conekta_oxxo', 'conekta_spei']:
            return res
        partner = self.partner_id
        if not partner and self.sale_order_ids:
            partner = self.sale_order_ids[0].partner_id
        if not partner and self.invoice_ids:
            partner = self.invoice_ids[0].partner_id
        partner_name = partner.name or self.partner_name or ''
        params = {
            'company': self.company_id.name,
            'provider': self.provider_id,
            'amount': processing_values['amount'],  # Mandatory
            'currency': self.currency_id,  # Mandatory anyway
            'name': partner_name.replace('_', ' '),
            'phone': partner.phone or partner.mobile or '',
            'email': partner.email or self.partner_email or '',
            'reference': self.reference,
        }
        if self.provider_code == 'conekta_oxxo':
            params.update({'api_url': '/payment/conekta_oxxo/feedback'})
        elif self.provider_code == 'conekta_spei':
            params.update({'api_url': '/payment/conekta_spei/feedback'})
        elif self.provider_code == 'conekta':
            params.update({'api_url': '/payment/conekta/feedback'})
        return params

    def _process_notification_data(self, notification_data):
        super()._process_notification_data(notification_data)
        if self.provider_code not in ['conekta', 'conekta_oxxo', 'conekta_spei']:
            return
        if self.provider_code == 'conekta' and notification_data.get('token_id'):
            self.token_id = notification_data.get('token_id')
 
        conekta.api_key = self.provider_id.conekta_secret_key_test if self.provider_id.state == 'test' else self.provider_id.conekta_secret_key
        params = self.create_params(self.provider_code)

        try:
            response = conekta.Order.create(params)
        except conekta.ConektaError as error:
            err_val = ''
            for err in error.error_json.get('details'):
                _logger.info(err)
                err_val += err.get('message') + '\n'
            self._set_error(err_val)
            _logger.info(err_val)

            return False
            # raise Warning(err_val)
        return self._conekta_s2s_validate_tree(response)
    
    def _send_payment_request(self):
        super()._send_payment_request()
        if self.provider_code != 'conekta':
            return

        if not self.token_id:
            raise UserError("Conekta: " + _("The transaction is not linked to a token."))

        _logger.info(
            "payment request response for transaction with reference %s:",
            self.reference
        )
        
        feedback_data = {'reference': self.reference, 'token_id': self.token_id}

        self._handle_notification_data(
            'conekta', feedback_data
        )

    @api.model
    def _conekta_form_get_tx_from_data(self, provider_code, notification_data):
        """ Given a data dict coming from conekta, verify it and find the related
        transaction record. """
        reference = notification_data.get('reference')  # data.get('metadata', {}).get('reference')
        if not reference:
            conekta_error = "No reference found in conekta transaction.."  # data.get('error', {}).get('message', '')
            _logger.error('Conekta: invalid reply received from Conekta API, looks like '
                          'the transaction failed. (error: %s)', conekta_error or 'n/a')
            error_msg = _("We're sorry to report that the transaction has failed.")
            if conekta_error:
                error_msg += " " + (_("Conekta gave us the following info about the problem: '%s'") %
                                    conekta_error)
            error_msg += " " + _("Perhaps the problem can be solved by double-checking your "
                                 "credit card details, or contacting your bank?")
            raise ValidationError(error_msg)

        tx = self.search([('reference', '=', reference), ('provider_code', '=', provider_code)])
        if not tx:
            error_msg = (_('Conekta: no order found for reference %s') % reference)
            _logger.error(error_msg)
            raise ValidationError(error_msg)
        elif len(tx) > 1:
            error_msg = (_('Conekta: %s orders found for reference %s') % (len(tx), reference))
            _logger.error(error_msg)
            raise ValidationError(error_msg)
        return tx[0]

    @api.model
    def _form_get_tx_from_data(self, provider_code, notification_data):
        reference, amount, currency_name = notification_data.get('reference'), notification_data.get('amount'), notification_data.get('currency_name')
        tx = self.search([('reference', '=', reference), ('provider_code', '=', provider_code)])

        if not tx or len(tx) > 1:
            error_msg = _('received data for reference %s') % (pprint.pformat(reference))
            if not tx:
                error_msg += _('; no order found')
            else:
                error_msg += _('; multiple order found')
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        return tx

    @api.model
    def _get_tx_from_notification_data(self, provider_code, notification_data):
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code not in ['conekta', 'conekta_oxxo', 'conekta_spei']:
            return tx
        if provider_code == 'conekta':
            tx = self._conekta_form_get_tx_from_data(provider_code, notification_data)
        else:
            tx = self._form_get_tx_from_data(provider_code, notification_data)
        return tx

    def _conekta_s2s_validate_tree(self, tree):
        self.ensure_one()
        if self.state not in ('draft', 'pending', 'refunding'):
            _logger.info('Conekta: trying to validate an already validated tx (ref %s)', self.reference)
            return True
        if type(tree) == dict and tree.get('error'):
            self._set_error(msg=tree.get('error'))
            return False

        status = tree.payment_status

        payment_tokens = self.mapped('token_id')

        if payment_tokens and 'src' not in payment_tokens.provider_ref:
            payment_tokens.sudo().write({'active': False, })

        if status == 'paid':
            # new_state = 'refunded' if self.state == 'refunding' else 'done'
            self.write({
                # 'state': new_state,
                # 'date': fields.datetime.now(),
                'provider_reference': tree.id,
            })
            self._set_done()
            if self.token_id:
                self.token_id.verified = True
            return True
        elif status == 'pending_payment':
            date = datetime.fromtimestamp(int(tree.charges[0].payment_method['expires_at'])).strftime('%Y-%m-%d')
            is_spei = self.provider_id.code == 'conekta_spei'
            reference = tree.charges[0].payment_method.clabe if is_spei else tree.charges[0].payment_method.reference
            vals = {
                'provider_reference': tree.id,
                'conekta_oxxo_reference': reference,
                'conekta_oxxo_expire_date': date,
            }
            if not is_spei:
                vals.update({'conekta_oxxo_barcode': base64.encodebytes(
                    requests.get(tree.charges[0].payment_method['barcode_url']).content),
                })
            if is_spei:
                vals.update({
                    'conekta_spei_receiving_account_number': tree.charges[0].payment_method.receiving_account_number,
                    'conekta_spei_receiving_account_bank': tree.charges[0].payment_method.receiving_account_bank,
                })
            self.write(vals)
            self._set_pending()
            if self.token_id:
                self.token_id.verified = True
            return True
        else:
            # error = tree['error']['message']
            # _logger.warn(error)
            self.sudo().write({
                'state_message': 'error',
                'provider_reference': tree.id,
                'date': fields.datetime.now(),
            })
            self._set_canceled()
            return False

    @api.model
    def get_speipay_brand_url(self):
        base_url = self.provider_id.get_base_url()
        if base_url[-1] == '/':
            base_url += 'payment_conekta_oxoo/static/src/img/spei_brand.png'
        else:
            base_url += '/payment_conekta_oxoo/static/src/img/spei_brand.png'
        return base_url

    def get_transaction_report_url(self, suffix=None, report_type=None, download=None, query_string=None, anchor=None):
        """
            Get a portal url for this model, including access_token.
            The associated route must handle the flags for them to have any effect.
            - suffix: string to append to the url, before the query string
            - report_type: report_type query string, often one of: html, pdf, text
            - download: set the download query string to true
            - query_string: additional query string
            - anchor: string to append after the anchor #
        """
        self.ensure_one()
        base_url = self.provider_id.get_base_url()
        if base_url[-1] != '/':
            base_url += '/'

        url = base_url + 'print_payment_transaction/' + str(self.id) + '%s?%s%s%s%s' % (
            suffix if suffix else '',
            '&report_type=%s' % report_type if report_type else '',
            '&download=true' if download else '',
            query_string if query_string else '',
            '#%s' % anchor if anchor else ''
        )
        return url

    @api.model
    def get_oxxopay_brand_url(self):
        base_url = self.provider_id.get_base_url()
        if base_url[-1] == '/':
            base_url += 'payment_conekta_oxoo/static/src/img/oxxopay_brand.png'
        else:
            base_url += '/payment_conekta_oxoo/static/src/img/oxxopay_brand.png'
        return base_url

    def _get_specific_processing_values(self, processing_values):
        """ Override of payment to return an access token as acquirer-specific processing values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic processing values of the transaction
        :return: The dict of acquirer-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_processing_values(processing_values)
        if self.provider_code != 'conekta':
            return res

        return {
            'access_token': payment_utils.generate_access_token(
                processing_values['reference'], processing_values['partner_id']
            )
        }

    def _get_report_base_filename(self):
        return 'Oxoo Recipt'
