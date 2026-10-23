package workplace;

import static org.junit.jupiter.api.Assertions.*;

import java.sql.SQLIntegrityConstraintViolationException;
import java.util.HashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.mindrot.jbcrypt.BCrypt;
import workplace.SimpleAuthServer.AuthService;
import workplace.SimpleAuthServer.JwtUtil;
import workplace.SimpleAuthServer.User;
import workplace.SimpleAuthServer.UserRepository;

class AuthServiceTest {
    private static final String PASSWORD = "Example-password-123";

    private static class MemoryUsers implements UserRepository {
        final Map<String, User> users = new HashMap<>();
        public void save(User user) throws Exception {
            if (users.containsKey(user.getEmployeeId())) {
                throw new SQLIntegrityConstraintViolationException("employee ID already exists");
            }
            user.setId((long) users.size() + 1);
            users.put(user.getEmployeeId(), user);
        }
        public User findByEmployeeId(String employeeId) { return users.get(employeeId); }
    }

    @Test
    void registrationStoresNameSeparatelyAndPreservesLeadingZeros() throws Exception {
        MemoryUsers users = new MemoryUsers();
        AuthService auth = new AuthService(users);
        auth.signUp(" 홍길동 ", " 000123 ", PASSWORD);
        User user = users.findByEmployeeId("000123");
        assertEquals("홍길동", user.getName());
        assertEquals("000123", user.getEmployeeId());
        assertNotEquals(PASSWORD, user.getPassword());
        assertTrue(BCrypt.checkpw(PASSWORD, user.getPassword()));
        assertEquals("홍길동", auth.login("000123", PASSWORD).getName());
        assertNull(auth.login("홍길동", PASSWORD));
        assertNull(auth.login("000123", "wrong-password"));
    }

    @Test
    void employeeIdMustBeUniqueButNamesMayRepeat() throws Exception {
        AuthService auth = new AuthService(new MemoryUsers());
        auth.signUp("홍길동", "001", PASSWORD);
        assertThrows(SQLIntegrityConstraintViolationException.class,
                () -> auth.signUp("김다른", "001", PASSWORD));
        assertDoesNotThrow(() -> auth.signUp("홍길동", "002", PASSWORD));
    }

    @Test
    void incompleteOrInvalidRegistrationIsRejectedBeforeWriting() {
        MemoryUsers users = new MemoryUsers();
        AuthService auth = new AuthService(users);
        assertThrows(IllegalArgumentException.class, () -> auth.signUp(" ", "001", PASSWORD));
        assertThrows(IllegalArgumentException.class, () -> auth.signUp("홍길동", " ", PASSWORD));
        assertThrows(IllegalArgumentException.class, () -> auth.signUp("홍길동", "00 1", PASSWORD));
        assertThrows(IllegalArgumentException.class, () -> auth.signUp("홍길동", "001", "short"));
        assertThrows(IllegalArgumentException.class, () -> auth.signUp("홍길동", "001", "가".repeat(25)));
        assertTrue(users.users.isEmpty());
    }

    @Test
    void jwtKeepsNameAndVoiceCompatibilityAndRestoresPersistedUser() throws Exception {
        MemoryUsers users = new MemoryUsers();
        AuthService auth = new AuthService(users);
        auth.signUp("홍길동", "000123", PASSWORD);
        User user = auth.login("000123", PASSWORD);
        String token = JwtUtil.createToken(user);
        assertEquals("홍길동", JwtUtil.verifyToken(token).getClaim("name").asString());
        assertEquals("000123", JwtUtil.verifyToken(token).getClaim("employeeId").asString());
        assertEquals("000123", JwtUtil.verifyToken(token).getClaim("username").asString());
        assertEquals("홍길동", JwtUtil.resolveUser(token, users).getName());
        user.setName("김변경");
        assertEquals("김변경", JwtUtil.resolveUser(token, users).getName());
        user.setId(999L);
        assertNull(JwtUtil.resolveUser(token, users));
        assertThrows(com.auth0.jwt.exceptions.JWTVerificationException.class,
                () -> JwtUtil.verifyToken(token + "invalid"));
    }

    @Test
    void profileJsonEscapesNameAndDoesNotExposePassword() throws Exception {
        User user = new User();
        user.setName("홍\"길\\동");
        user.setEmployeeId("000123");
        user.setPassword("never-return-this");
        String json = SimpleAuthServer.userJson(user);
        assertEquals("{\"name\":\"홍\\\"길\\\\동\",\"employeeId\":\"000123\"}", json);
        assertFalse(json.contains("password"));
        assertFalse(json.contains("never-return-this"));
    }
}
