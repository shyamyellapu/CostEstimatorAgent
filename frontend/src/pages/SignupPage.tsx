import AuthLayout from '../components/auth/AuthLayout'
import SignupForm from '../components/auth/SignupForm'

export default function SignupPage() {
  return (
    <AuthLayout title="Create your account" subtitle="Get started with AI-powered cost estimating.">
      <SignupForm />
    </AuthLayout>
  )
}
