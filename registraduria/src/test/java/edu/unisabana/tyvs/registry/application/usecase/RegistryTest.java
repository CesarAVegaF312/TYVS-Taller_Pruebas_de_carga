package edu.unisabana.tyvs.registry.application.usecase;

import edu.unisabana.tyvs.registry.application.port.out.RegistryRepositoryPort;
import edu.unisabana.tyvs.registry.domain.model.Gender;
import edu.unisabana.tyvs.registry.domain.model.Person;
import edu.unisabana.tyvs.registry.domain.model.RegisterResult;
import edu.unisabana.tyvs.registry.infrastructure.persistence.RegistryRepository;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Pruebas de integración para el caso de uso {@link Registry}, aplicando el formato AAA:
 * <ul>
 *   <li><b>Arrange</b>: preparación de datos y objetos a probar.</li>
 *   <li><b>Act</b>: ejecución del método bajo prueba.</li>
 *   <li><b>Assert</b>: verificación de los resultados esperados.</li>
 * </ul>
 */
class RegistryTest {

    private RegistryRepositoryPort repo;
    private Registry registry;

    /**
     * Arrange común a todos los tests:
     * <ul>
     *   <li>Instancia un repositorio H2 en memoria.</li>
     *   <li>Inicializa el esquema (tabla) y limpia datos previos.</li>
     *   <li>Construye el caso de uso inyectando el repositorio.</li>
     * </ul>
     */
    @BeforeEach
    void setup() throws Exception {
        String jdbc = "jdbc:h2:mem:regdb;DB_CLOSE_DELAY=-1";
        repo = new RegistryRepository(jdbc);

        repo.initSchema();   // Arrange: crear tabla
        repo.deleteAll();    // Arrange: limpiar datos previos

        registry = new Registry(repo); // Arrange: inyectar dependencia
    }

    /**
     * Caso de prueba:
     * <p>Una persona válida debe ser registrada exitosamente.</p>
     */
    @Test
    void shouldRegisterValidPerson() throws Exception {
        // Arrange
        Person p1 = new Person("Ana", 100, 30, Gender.FEMALE, true);

        // Act
        RegisterResult result = registry.registerVoter(p1);

        // Assert
        assertEquals(RegisterResult.VALID, result);
        assertTrue(repo.existsById(100));
    }

    /**
     * Caso de prueba:
     * <p>Al intentar registrar dos personas con el mismo ID:</p>
     * <ul>
     *   <li>La primera se guarda como válida.</li>
     *   <li>La segunda es rechazada como duplicada.</li>
     * </ul>
     */
    @Test
    void shouldPersistValidVoterAndRejectDuplicates() throws Exception {
        // Arrange
        Person p1 = new Person("Ana", 100, 30, Gender.FEMALE, true);
        Person p2 = new Person("AnaDos", 100, 40, Gender.FEMALE, true);

        // Act (primer registro)
        RegisterResult result1 = registry.registerVoter(p1);

        // Assert primer registro
        assertEquals(RegisterResult.VALID, result1);
        assertTrue(repo.existsById(100));

        // Act (segundo registro con mismo ID)
        RegisterResult result2 = registry.registerVoter(p2);

        // Assert segundo registro
        assertEquals(RegisterResult.DUPLICATED, result2);
    }
}
