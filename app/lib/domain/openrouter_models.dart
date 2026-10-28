/// Presety modeli OpenRouter do wyjaśnień.
class OpenRouterModelOption {
  const OpenRouterModelOption(this.label, this.modelId, {this.reasoningEffort});

  final String label;
  final String modelId;

  /// Poziom reasoning (OpenRouter `reasoning.effort`); null = bez parametru.
  final String? reasoningEffort;
}

class OpenRouterModels {
  OpenRouterModels._();

  static const defaultModelId = 'google/gemini-2.5-flash';

  static const presets = [
    OpenRouterModelOption('Gemini 2.5 Flash', 'google/gemini-2.5-flash'),
    OpenRouterModelOption('Qwen3.6 Plus', 'qwen/qwen3.6-plus'),
    OpenRouterModelOption('DeepSeek V3.2', 'deepseek/deepseek-v3.2'),
    OpenRouterModelOption('DeepSeek V4 Flash', 'deepseek/deepseek-v4-flash'),
    OpenRouterModelOption('Grok 4.3', 'x-ai/grok-4.3'),
    OpenRouterModelOption(
      'GPT 6.1 Sol (Medium)',
      'openai/gpt-6.1-sol',
      reasoningEffort: 'medium',
    ),
    OpenRouterModelOption(
      'Claude Sonnet 5.5 (Medium)',
      'anthropic/claude-sonnet-5.5',
      reasoningEffort: 'medium',
    ),
  ];

  static OpenRouterModelOption byModelId(String id) {
    return presets.firstWhere(
      (p) => p.modelId == id,
      orElse: () => presets.first,
    );
  }
}
