package edu.unisabana.tyvs.registry.delivery.rest;

import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * Traduce los errores del cliente a 400 en lugar de 500.
 *
 * Sin esta clase, un genero fuera del enum (por ejemplo "X") produce un
 * IllegalArgumentException dentro de Gender.valueOf() y Spring responde 500.
 * Eso es incorrecto: 5xx significa "el servidor fallo", cuando quien se
 * equivoco fue el cliente.
 *
 * Importa especialmente en este taller: http_req_failed de k6 cuenta los 5xx
 * como fallos del sistema. Un dato mal formado en el CSV de carga apareceria
 * como "el servidor falla bajo carga", y el diagnostico iria a buscar hilos o
 * conexiones agotadas donde solo habia una fila mal escrita.
 */
@RestControllerAdvice
public class RegistryExceptionHandler {

    /** Genero fuera del enum, o cualquier argumento invalido del cliente. */
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<String> handleInvalidArgument(IllegalArgumentException ex) {
        return ResponseEntity.badRequest().body("INVALID_INPUT");
    }

    /** JSON mal formado o con tipos que no encajan en el DTO. */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<String> handleMalformedJson(HttpMessageNotReadableException ex) {
        return ResponseEntity.badRequest().body("MALFORMED_JSON");
    }
}
