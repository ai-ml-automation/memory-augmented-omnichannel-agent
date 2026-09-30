import { describe, it, expect } from 'vitest';
import { loginSchema, registerSchema, consentSchema } from './validations';

const TEST_PASS = 'testPass123456';
const MISMATCH_PASS = 'differentPass999';

describe('loginSchema', () => {
  it('valid phone and password', () => {
    const result = loginSchema.safeParse({
      phone: '+7 (999) 123-45-67',
      password: TEST_PASS,
    });
    expect(result.success).toBe(true);
  });

  it('rejects invalid phone', () => {
    const result = loginSchema.safeParse({
      phone: '12345',
      password: TEST_PASS,
    });
    expect(result.success).toBe(false);
  });

  it('rejects short password', () => {
    const result = loginSchema.safeParse({
      phone: '+7 (999) 123-45-67',
      password: '123',
    });
    expect(result.success).toBe(false);
  });

  it('rejects empty phone', () => {
    const result = loginSchema.safeParse({
      phone: '',
      password: TEST_PASS,
    });
    expect(result.success).toBe(false);
  });
});

describe('registerSchema', () => {
  it('valid registration data', () => {
    const result = registerSchema.safeParse({
      phone: '+7 (999) 123-45-67',
      password: TEST_PASS,
      confirmPassword: TEST_PASS,
      fullName: 'Иван Иванов',
    });
    expect(result.success).toBe(true);
  });

  it('rejects mismatched passwords', () => {
    const result = registerSchema.safeParse({
      phone: '+7 (999) 123-45-67',
      password: TEST_PASS,
      confirmPassword: MISMATCH_PASS,
      fullName: 'Иван Иванов',
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const confirmPasswordError = result.error.issues.find(
        (i) => i.path.includes('confirmPassword')
      );
      expect(confirmPasswordError).toBeDefined();
    }
  });

  it('works without fullName (optional)', () => {
    const result = registerSchema.safeParse({
      phone: '+7 (999) 123-45-67',
      password: TEST_PASS,
      confirmPassword: TEST_PASS,
    });
    expect(result.success).toBe(true);
  });
});

describe('consentSchema', () => {
  it('valid consent', () => {
    const result = consentSchema.safeParse({
      purpose: 'Персонализация ответов',
      legal_basis: 'Согласие субъекта (ч. 1 ст. 9 152-ФЗ)',
    });
    expect(result.success).toBe(true);
  });

  it('rejects empty purpose', () => {
    const result = consentSchema.safeParse({
      purpose: '',
      legal_basis: 'Согласие субъекта (ч. 1 ст. 9 152-ФЗ)',
    });
    expect(result.success).toBe(false);
  });
});
