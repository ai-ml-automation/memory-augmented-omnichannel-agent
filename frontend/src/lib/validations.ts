/**
 * Zod validation schemas for forms (Phase G.1)
 */
import { z } from 'zod';

export const loginSchema = z.object({
  phone: z
    .string()
    .min(1, 'Введите номер телефона')
    .regex(/^\+7\s?\(?\d{3}\)?\s?\d{3}[-\s]?\d{2}[-\s]?\d{2}$/, 'Формат: +7 (999) 123-45-67'),
  password: z
    .string()
    .min(6, 'Пароль должен быть не менее 6 символов'),
});

export type LoginFormData = z.infer<typeof loginSchema>;

export const registerSchema = z.object({
  phone: z
    .string()
    .min(1, 'Введите номер телефона')
    .regex(/^\+7\s?\(?\d{3}\)?\s?\d{3}[-\s]?\d{2}[-\s]?\d{2}$/, 'Формат: +7 (999) 123-45-67'),
  password: z
    .string()
    .min(6, 'Пароль должен быть не менее 6 символов'),
  confirmPassword: z
    .string()
    .min(1, 'Подтвердите пароль'),
  full_name: z
    .string()
    .min(2, 'Имя должно быть не менее 2 символов')
    .optional()
    .or(z.literal('')),
}).refine((data) => data.password === data.confirmPassword, {
  message: 'Пароли не совпадают',
  path: ['confirmPassword'],
});

export type RegisterFormData = z.infer<typeof registerSchema>;

export const consentSchema = z.object({
  purpose: z
    .string()
    .min(1, 'Укажите цель обработки'),
  legal_basis: z
    .string()
    .min(1, 'Укажите правовое основание'),
});

export type ConsentFormData = z.infer<typeof consentSchema>;
