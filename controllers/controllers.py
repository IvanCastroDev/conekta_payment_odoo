# -*- coding: utf-8 -*-
import logging
import pprint

from odoo.addons.payment import utils as payment_utils
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo import _


from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

from odoo.addons.website_sale.controllers.main import WebsiteSale

try:
    import phonenumbers
except ImportError:
    phonenumbers = None


class WebsiteSaleConekta(WebsiteSale):
    def checkout_form_validate(self, mode, all_form_values, data):
        error, error_message = super(WebsiteSaleConekta, self).checkout_form_validate(mode, all_form_values, data)
        if 'phone' not in error and all_form_values.get('phone'):
            phone = all_form_values.get('phone')
            if len(phone) < 10:
                error['phone'] = 'error'
                error_message.append('Please enter valid phone number. Length of phone number must be 10 digits')
        return error, error_message


class PortalConekta(CustomerPortal):

    @http.route(['/print_payment_transaction/<int:transaction_id>'], type='http', auth="public", website=True)
    def portal_payment_transaction_detail(self, transaction_id, report_type=None, download=False, **kw):
        document = request.env['payment.transaction'].sudo().browse(transaction_id)
        document_sudo = document.exists()
        if not document_sudo:
            # raise MissingError("This document does not exist.")
            return request.redirect('/my')
        # if report_type in ('html', 'pdf', 'text'):
        if document_sudo.provider_id.code == 'conekta_spei':
            return self._show_report(model=document_sudo, report_type=report_type,
                                     report_ref='payment_conekta_oxoo.action_report_payment_transaction_spei',
                                     download=download)
        else:
            return self._show_report(model=document_sudo, report_type=report_type,
                                     report_ref='payment_conekta_oxoo.action_report_payment_transaction',
                                     download=download)


class Conekta(http.Controller):
    _accept_url = '/payment/transfer/feedback'

    @http.route([
        '/payment/conekta_oxxo/feedback',
    ], type='http', auth='public', csrf=False)
    def conekta_oxxo_form_feedback(self, **post):
        _logger.info('Beginning form_feedback with post data %s', pprint.pformat(post))
        request.env['payment.transaction'].sudo()._handle_notification_data("conekta_oxxo", post)
        return request.redirect('/payment/status')

    @http.route([
        '/payment/conekta_spei/feedback',
    ], type='http', auth='public', csrf=False)
    def conekta_spei_form_feedback(self, **post):
        _logger.info('Beginning form_feedback with post data %s', pprint.pformat(post))
        request.env['payment.transaction'].sudo()._handle_notification_data("conekta_spei", post)
        return request.redirect('/payment/status')

    @http.route(['/payment/conekta/oxoo_pay/create'], type='json', auth='public')
    def conekta_oxoo_pay_create_charge(self, **post):
        _logger.info('post : ' + str(post))
        #import pdb; pdb.set_trace();
        json_data = request.get_json_data()
        _logger.info("json_data :" + str(json_data))
        data = json_data.get('data')
        if json_data and json_data.get('type', '') == 'charge.paid' and data:
            tx_obj = request.env['payment.transaction']
            order_id = data.get('object', {}).get('order_id')
            payment_reference = data.get('object', {}).get('payment_method', {}).get('reference')
            tx = None
            if order_id:
                tx = tx_obj.sudo().search([('provider_reference', '=', order_id)], limit=1)
            if not tx and payment_reference:
                tx = tx_obj.sudo().search([('conekta_oxxo_reference', '=', payment_reference)], limit=1)
            if tx:
                if tx.state in ['pending', 'draft']:
                    tx._set_done()
                try:
                    tx._finalize_post_processing()
                except Exception as e:
                    pass
        return "<Response></Response>"
    #
    # @http.route(['/payment/conekta/s2s/create_json'], type='json', auth='public')
    # def conekta_s2s_create_json(self, **kwargs):
    #     acquirer_id = int(kwargs.get('acquirer_id'))
    #     acquirer = request.env['payment.acquirer'].browse(acquirer_id)
    #     if not kwargs.get('partner_id'):
    #         kwargs = dict(kwargs, partner_id=request.env.user.partner_id.id)
    #     return acquirer.s2s_process(kwargs).id
    #
    # @http.route(['/payment/conekta/s2s/create'], type='http', auth='public')
    # def conekta_s2s_create(self, **post):
    #     acquirer_id = int(post.get('acquirer_id'))
    #     acquirer = request.env['payment.acquirer'].browse(acquirer_id)
    #     error = None
    #     try:
    #         acquirer.s2s_process(post)
    #     except Exception as e:
    #         error = e.message
    #
    #     return_url = post.get('return_url', '/')
    #     if error:
    #         separator = '?' if werkzeug.urls.url_parse(return_url).query == '' else '&'
    #         return_url += '{}{}'.format(separator, werkzeug.urls.url_encode({'error': error}))
    #
    #     return werkzeug.utils.redirect(return_url)

    @http.route(['/payment/conekta/s2s/create_json_3ds'], type='json', auth='public', csrf=False)
    def conekta_s2s_create_json_3ds(self, verify_validity=False, **kwargs):
        if not kwargs.get('partner_id'):
            kwargs = dict(kwargs, partner_id=request.env.user.partner_id.id)
        token = request.env['payment.provider'].browse(int(kwargs.get('provider_id'))).conekta_s2s_form_process(kwargs)

        if not token:
            res = {
                'result': False,
            }
            return res
        res = {
            'result': True,
            'id': token.id,
            'short_name': token.provider_ref.replace('XXXXXXXXXXXX', '***'),
            'verified': False,
        }

        if verify_validity != False:
            token.validate()
            res['verified'] = token.verified

        return res

    @http.route('/payment/conekta/payment', type='json', auth='public')
    def conekta_authorize_payment(self, reference, partner_id, access_token, token_id, opaque_data=None):
        """ Make a payment request and handle the response.

        :param str reference: The reference of the transaction
        :param int partner_id: The partner making the transaction, as a `res.partner` id
        :param str access_token: The access token used to verify the provided values
        :param dict opaque_data: The payment details
        :return: None
        """
        # Check that the transaction details have not been altered
        if not payment_utils.check_access_token(access_token, reference, partner_id):
            raise ValidationError("Conekta: " + _("Received tampered payment request data."))

        tx_sudo = request.env['payment.transaction'].sudo().search([('reference', '=', reference)])
        feedback_data = {'reference': tx_sudo.reference, 'token_id': token_id}
        request.env['payment.transaction'].sudo()._handle_notification_data(
            'conekta', feedback_data
        )
