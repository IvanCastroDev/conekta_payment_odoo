odoo.define('payment_conekta_oxoo.safari_error' , require => {
    const {browser} = require("@web/core/browser/browser");
    const {UncaughtClientError} = require("@web/core/errors/error_service");


    window.onerror = function(message, source, lineno, colno, error) {
        if (message.includes("Attempted to assign to readonly property")) {
            console.log('Error de propiedad solo lectura capturado:');
            console.log(`Mensaje: ${message}`);
            console.log(`Archivo: ${source}`);
            console.log(`Línea: ${lineno}`);
            console.log(`Columna: ${colno}`);  
            console.log(`Error objeto:`, error);
    
            // Evita que el navegador muestre el mensaje de error predeterminado
            return true;
        }
    };
});
