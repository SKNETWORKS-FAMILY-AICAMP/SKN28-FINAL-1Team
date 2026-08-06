import { AuthEndpoints } from '@/constants/config';
import { api, ApiError } from '@/lib/apiClient';
import { authStore, type AuthUser } from '@/state/auth';

type EmailAuthResponse = {
  access: string;
  refresh: string;
  user: AuthUser;
  is_new_user: boolean;
};

async function finishEmailAuth(path: string, email: string, password: string) {
  const response = await api.post<EmailAuthResponse>(
    path,
    { email: email.trim().toLowerCase(), password },
    { auth: false },
  );
  await authStore.signIn(
    { access: response.access, refresh: response.refresh },
    response.user,
  );
  return response;
}

export function signupWithEmail(email: string, password: string) {
  return finishEmailAuth(AuthEndpoints.signup, email, password);
}

export function loginWithEmail(email: string, password: string) {
  return finishEmailAuth(AuthEndpoints.login, email, password);
}

export function emailAuthErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return '서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.';

  const data = error.data as Record<string, unknown> | null;
  if (data) {
    for (const key of ['email', 'password', 'non_field_errors']) {
      const value = data[key];
      if (Array.isArray(value) && typeof value[0] === 'string') return value[0];
      if (typeof value === 'string') return value;
    }
  }
  return error.message;
}
