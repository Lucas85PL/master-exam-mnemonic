import 'package:flutter_test/flutter_test.dart';
import 'package:memonic_app/data/explain_service.dart';
import 'package:memonic_app/data/question_repository.dart';
import 'package:memonic_app/domain/explain_prompt.dart';
import 'package:memonic_app/domain/openrouter_models.dart';

void main() {
  test('buildExplainUserPrompt includes question and correct letter', () {
    final q = QuestionRow(
      id: 1,
      pytanie: 'Co to jest COLREG?',
      poprawnaOdpowiedz: 'B',
      odpA: 'SOLAS',
      odpB: 'Przepisy COLREG',
      odpC: null,
      odpD: null,
    );
    final prompt = buildExplainUserPrompt(
      question: q,
      userPicked: 'A',
      userWasCorrect: false,
    );
    expect(prompt, contains('Co to jest COLREG?'));
    expect(prompt, contains('Poprawna odpowiedź: B'));
    expect(prompt, contains('Użytkownik wybrał: A'));
  });

  test('system prompt asks for answer verification and warning prefix', () {
    final p = buildExplainSystemPrompt();
    expect(explainWarningPrefix, 'UWAGA - ODP. W BAZIE DANYCH MOŻE BYĆ BŁĘDNA');
    expect(p, contains('"agree"'));
    expect(p, contains('OCR'));
    for (final doc in ['Kodeks morski', 'STCW', 'COLREG', 'MARPOL', 'ISM Code', 'LSA Code', 'FFE Code', 'MLC', 'UNCLOS', 'ISPS Code', 'IMDG Code']) {
      expect(p, contains(doc));
    }
  });

  test('new presets carry medium reasoning effort', () {
    for (final id in ['openai/gpt-6.1-sol', 'anthropic/claude-sonnet-5.5']) {
      expect(OpenRouterModels.byModelId(id).modelId, id);
      expect(OpenRouterModels.byModelId(id).reasoningEffort, 'medium');
    }
  });

  test('formatExplanation: zgodna odpowiedz -> prefiks bez ostrzezenia', () {
    final out = formatExplanation(
        '{"my_answer":"B","agree":true,"explanation":"Bo tak."}', 'B');
    expect(out, 'Prawidłowa odpowiedź to B. Bo tak.');
  });

  test('formatExplanation: model zgodny co do litery, ale agree=false -> ostrzezenie', () {
    final out = formatExplanation(
        '```json\n{"my_answer":"B","agree":false,"explanation":"Watpliwosc."}\n```',
        'B');
    expect(out, startsWith(explainWarningPrefix));
  });

  test('formatExplanation: inna litera -> ostrzezenie, nawet gdy agree=true', () {
    final out = formatExplanation(
        '{"my_answer":"C","agree":true,"explanation":"x"}', 'B');
    expect(out, startsWith(explainWarningPrefix));
  });

  test('formatExplanation: tekst nie-JSON przechodzi bez zmian', () {
    expect(formatExplanation('  zwykly tekst ', 'A'), 'zwykly tekst');
  });

  test('contentHash changes when answer text changes', () {
    final q1 = QuestionRow(
      id: 1,
      pytanie: 'Test',
      poprawnaOdpowiedz: 'A',
      odpA: 'one',
      odpB: 'two',
      odpC: null,
      odpD: null,
    );
    final q2 = QuestionRow(
      id: 1,
      pytanie: 'Test',
      poprawnaOdpowiedz: 'A',
      odpA: 'one',
      odpB: 'changed',
      odpC: null,
      odpD: null,
    );
    expect(ExplainService.contentHash(q1), isNot(ExplainService.contentHash(q2)));
  });
}
