odoo.define('payment_conekta_oxoo.payment_form' , require => {
    "use strict";
    const core = require('web.core');
    const PaymentForm = require('payment.checkout_form');
    const manageForm = require('payment.manage_form');
    const _t = core._t;

    const conektaMixin = {
        _conektaResponseHandler: function (providerId, tokenId) {
            // Create the transaction and retrieve the processing values
            return this._rpc({
                route: this.txContext.transactionRoute,
                params: this._prepareTransactionRouteParams('contekta', providerId, 'direct'),
            }).then(processingValues => {
                // Initiate the payment
                return this._rpc({
                    route: '/payment/conekta/payment',
                    params: {
                        'reference': processingValues.reference,
                        'partner_id': processingValues.partner_id,
                        'access_token': processingValues.access_token,
                        'token_id': tokenId,
//                        'opaque_data': response.opaqueData,
                    }
                }).then(() => window.location = '/payment/status');
            }).guardedCatch((error) => {
                error.event.preventDefault();
                this._displayError(
                    _t("Server Error"),
                    _t("We are not able to process your payment."),
                    error.message.data.message
                );
            });
        },

        getFormData: function ($form) {
            var unindexed_array = $form.serializeArray();
            var indexed_array = {};

            $.map(unindexed_array, function (n, i) {
                indexed_array[n.name] = n.value;
            });
            return indexed_array;
        },

       _createConektaToken: function ($checkedRadio, addPmEvent) {
            var self = this;
//            var form = this.el
            $checkedRadio = $checkedRadio[0];
            var providerID = $checkedRadio.dataset.paymentOptionId;
            var providerForm = this.$('#o_payment_provider_inline_form_' + providerID);
            var inputsForm = $('input', providerForm);
            var formData = self.getFormData(inputsForm);
            var ds = $('input[name="data_set"]', providerForm)[0];

            var conektaSuccessResponseHandler = function(token) {

                formData['conekta_token'] = token.id
                var customerID = '';
                
                if (formData['o_payment_save_as_token']) {
                    self._rpc({
                        route: '/payment/conekta/s2s/create_client',
                        params: {'provider_id': providerID, 'tokenId': token.id}
                    }).then(function(response) {
                        console.log(response);
                        customerID = response.id;
                    });
                }
                
                return self._rpc({
                    route: ds.dataset.createRoute,
                    params: formData,
                }).then(function (data) {
                    // if the server has returned true
                    if (data.result) {
//                        $checkedRadio.value = data.id; // set the radio value to the new card id
                        return self._conektaResponseHandler(parseInt(formData.provider_id), data.id);
                    }
                    // if the server has returned false, we display an error
                    else {
                        if (data.error) {
                            self.displayError(
                                '',
                                data.error);
                        } else { // if the server doesn't provide an error message
                            self._displayError(
                                _t('Server Error'),
                                _t('e.g. Your credit card details are wrong. Please verify.'));
                        }
                    }
                }).guardedCatch(function (error) {
                    error.event.preventDefault();
                    self._displayError(
                        _t('Server Error'),
                        _t("We are not able to add your payment method at the moment."),
                        error.message.data.message
                    );
                });
                //###########################

            };
            var conektaErrorResponseHandler = function(response) {
                self._displayError('',response.message_to_purchaser);
            };
            if (formData.cc_expiry_yy.length == 4){
                var exp_year = formData.cc_expiry_yy
            }
            else{
                var exp_year = new Date().getFullYear().toString().substr(0,2) + formData.cc_expiry_yy
            }
            var tokenParams = {
                      "card": {
                        "number": formData.cc_number,
                        "name": formData.cc_holder_name,
                        "exp_year": exp_year,
                        "exp_month": formData.cc_expiry_mm,
                        "cvc": formData.cvc,
                      }
                    };

            /* Conekta.setPublicKey(formData.conekta_public_key);
            Conekta.Token.create(tokenParams, conektaSuccessResponseHandler, conektaErrorResponseHandler); */

            const options = {
                backgroundMode: 'lightMode', //lightMode o darkMode
                colorPrimary: '#081133', //botones y bordes
                colorText: '#585987', // títulos
                colorLabel: '#585987', // input labels
                inputType: 'minimalMode', // minimalMode o flatMode
                };

            const config = {
                locale: 'es',
                publicKey: '{{yourKey}}',
                targetIFrame: '#example',
            };
        
            const callbacks = {
                // Evento que permitirá saber que el token se creado de forma satisfactoria, es importante que se consuman los datos que de él derivan.
                onCreateTokenSucceeded: function (token) {
                    console.log('token', token);
                },
                // Evento que permitirá saber que el token se creado de manera incorrecta, es importante que se consuman los datos que de él derivan y se hagan las correciones pertinentes.
                onCreateTokenError: function (error) {
                    console.log(error);
                },
                // Evento que notifica cuando finalizó la carga del component/tokenizer
                onGetInfoSuccess: function (loadingTime) {
                    console.log('loading time en milisegundos', loadingTime.initLoadTime);
                }
            };
            
            window.ConektaCheckoutComponents.Card({
                config,
                callbacks,
                options
            });
        },

      async _processPayment(provider, paymentOptionId, flow) {
            if (provider !== 'conekta' || flow === 'token') {
                return this._super(...arguments); // Tokens are handled by the generic flow
            }
            var $checkedRadio = this.$('input[type="radio"]:checked');
            this._createConektaToken($checkedRadio);
        },

    };

    PaymentForm.include(conektaMixin);
    manageForm.include(conektaMixin);
});
