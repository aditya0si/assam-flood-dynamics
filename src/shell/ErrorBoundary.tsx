import { Component, type ErrorInfo, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(_error: Error, _info: ErrorInfo): void {
    // The fallback is the report; do not write to the console in acceptance runs.
  }

  render() {
    if (this.state.hasError) {
      return (
        <main style={{ padding: '2rem', color: '#e7f0f4', background: '#071014', minHeight: '100dvh' }}>
          <h1 style={{ margin: 0, fontSize: '1.2rem' }}>Baanh could not render</h1>
          <p style={{ color: '#8aa2ad', maxWidth: '54ch' }}>
            The application hit an unexpected rendering error. This is not a forecast or a warning
            service; reload the page to retry the committed dataset.
          </p>
        </main>
      );
    }
    return this.props.children;
  }
}
