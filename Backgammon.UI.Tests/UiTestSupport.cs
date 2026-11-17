using System;
using Backgammon.Core;

namespace Backgammon.UI.Tests
{
    /// <summary>
    /// Deterministik, ONNX bagimsiz sahte degerlendirici.
    /// </summary>
    /// <remarks>
    /// <b>Neden sahte?</b> <c>Backgammon.UI</c> bilincli olarak <c>Backgammon.Inference</c>'a referans
    /// vermez (Faz 5 Bolum 2.1). Test 32/33 determinizm ve iptal davranisini olcer; model kalitesini
    /// degil. Bu yuzden deger, tahtanin saf bir fonksiyonudur ve her cagride ayni sonucu verir.
    /// </remarks>
    internal sealed class FakeEvaluator : IPolicyValueEvaluator, ICombinedBatchEvaluator
    {
        public int Version
        {
            get { return 1; }
        }

        public int EvaluateCalls;
        public int ScoreCalls;

        /// <summary>Degerlendirmenin calistigi son is parcacigi kimligi (Test 33).</summary>
        public int LastThreadId;

        /// <summary>Yalnizca ilk cagride uygulanacak yapay gecikme (ms); es zamanlilik testi icin.</summary>
        public int DelayFirstCallMs;

        public void EvaluateBatch(
            AfterStateList list, int offset, int count, int perspective,
            in VectorizerScalars scalars, Span<float> results)
        {
            EvaluateCalls++;
            LastThreadId = System.Threading.Thread.CurrentThread.ManagedThreadId;
            if (DelayFirstCallMs > 0)
            {
                int delay = DelayFirstCallMs;
                DelayFirstCallMs = 0;
                System.Threading.Thread.Sleep(delay);
            }

            for (int i = 0; i < count; i++)
            {
                results[i] = Score(list.BoardOf(offset + i), perspective);
            }
        }

        public void ScoreBatch(
            AfterStateList list, int offset, int count, int perspective,
            in VectorizerScalars scalars, Span<float> results)
        {
            ScoreCalls++;
            for (int i = 0; i < count; i++)
            {
                results[i] = 0.0f;
            }
        }

        public void EvaluateAndScoreBatch(
            AfterStateList list, int offset, int count, int perspective,
            in VectorizerScalars scalars, Span<float> values, Span<float> scores)
        {
            EvaluateBatch(list, offset, count, perspective, scalars, values);
            ScoreBatch(list, offset, count, perspective, scalars, scores);
        }

        /// <summary>Pip farkindan turetilen, [-3, 3] araligina kirpilmis deterministik deger.</summary>
        public static float Score(ReadOnlySpan<sbyte> board, int perspective)
        {
            int active = 0;
            int opponent = 0;
            for (int p = 1; p <= 24; p++)
            {
                int v = board[p];
                if (v > 0)
                {
                    active += v * (25 - p);
                }
                else if (v < 0)
                {
                    opponent += -v * p;
                }
            }

            active += board[0] * 25;
            opponent += -board[25] * 25;

            double diff = perspective > 0 ? opponent - active : active - opponent;
            double value = diff / 100.0;
            if (value > 3.0)
            {
                value = 3.0;
            }
            else if (value < -3.0)
            {
                value = -3.0;
            }

            return (float)value;
        }
    }

    /// <summary>Test yardimcilari.</summary>
    internal static class UiTestSupport
    {
        /// <summary>Standart baslangic dizilimi.</summary>
        public static BackgammonState InitialState()
        {
            var state = new BackgammonState();
            state.Reset();
            return state;
        }

        /// <summary>Verilen seed ile yeni bir uretici.</summary>
        public static Xoshiro256StarStar Random(ulong seed)
        {
            return new Xoshiro256StarStar(seed);
        }

        /// <summary>Tahtayi sifirlar ve verilen dizilimi uygular.</summary>
        public static void SetBoard(BackgammonState state, int[] white, int[] black)
        {
            for (int i = 0; i < BackgammonState.BoardSize; i++)
            {
                state.board[i] = 0;
            }

            for (int p = 1; p <= 24; p++)
            {
                state.board[p] = (sbyte)(white[p] - black[p]);
            }

            state.whiteBorneOff = 0;
            state.blackBorneOff = 0;
        }

        /// <summary>Rastgele yasal hamlelerle ilerleyerek <paramref name="count"/> adet "Moving" fazi durumu uretir.</summary>
        public static System.Collections.Generic.List<BackgammonState> RandomMovingPositions(int count, ulong seed)
        {
            var result = new System.Collections.Generic.List<BackgammonState>(count);
            var rng = new Xoshiro256StarStar(seed);
            var state = InitialState();
            var moves = new MoveList();

            int guard = 0;
            while (result.Count < count && guard++ < 200000)
            {
                if (state.phase == GamePhase.GameOver)
                {
                    state.Reset();
                    continue;
                }

                if (state.phase == GamePhase.DetermineFirstPlayer)
                {
                    BackgammonEngine.RollOpening(state, rng);
                    continue;
                }

                if (state.phase == GamePhase.PreRoll || state.phase == GamePhase.WaitForRoll)
                {
                    BackgammonEngine.RollDice(state, rng);
                    continue;
                }

                if (state.phase != GamePhase.Moving)
                {
                    state.Reset();
                    continue;
                }

                result.Add(state.Clone());

                LegalMoveGenerator.GenerateAllLegalMoves(state, moves);
                if (moves.Count == 0)
                {
                    BackgammonEngine.PassTurn(state);
                    continue;
                }

                int pick = (int)(rng.NextUInt() % (uint)moves.Count);
                BackgammonEngine.ApplyMove(state, moves[pick]);
            }

            return result;
        }
    }
}
