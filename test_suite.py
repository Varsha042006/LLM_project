import os
import sys
import unittest
import numpy as np
import torch

# Environment setup
os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
if "tensorflow" not in sys.modules:
    sys.modules["tensorflow"] = None

from tokenizer import load_tokenizer, tokenize_text, format_step4_flow
from model import (
    load_model,
    get_model_metadata,
    extract_embeddings,
    forward_xray,
    compute_logits_and_probs,
    generate_with_xray_trace
)
from visualization import (
    create_pca_embedding_plot,
    create_embedding_heatmap_matrix,
    create_attention_heatmap,
    create_hidden_states_pca_trajectory,
    create_logits_bar_chart,
    create_step_generation_flow
)


class TestTokenizer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokenizer = load_tokenizer("Qwen/Qwen2.5-0.5B-Instruct")

    def test_load_tokenizer(self):
        self.assertIsNotNone(self.tokenizer)
        self.assertIsNotNone(self.tokenizer.pad_token)

    def test_tokenize_text(self):
        tokens = tokenize_text(self.tokenizer, "Hello world!")
        self.assertGreater(len(tokens), 0)
        self.assertEqual(tokens[0]["index"], 0)
        self.assertIn("token_id", tokens[0])
        self.assertIn("display_token", tokens[0])

    def test_tokenize_empty(self):
        tokens = tokenize_text(self.tokenizer, "")
        self.assertEqual(tokens, [])

    def test_format_step4_flow(self):
        tokens = tokenize_text(self.tokenizer, "What is AI?")
        flow = format_step4_flow(tokens)
        self.assertIn("tokens_str", flow)
        self.assertIn("ids_str", flow)
        self.assertTrue(len(flow["tokens_str"]) > 0)
        self.assertTrue(len(flow["ids_str"]) > 0)


class TestModelAndInference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model_name = "Qwen/Qwen2.5-0.5B-Instruct"
        cls.model, cls.tokenizer, cls.device = load_model(cls.model_name, device="cpu")
        cls.metadata = get_model_metadata(cls.model)

    def test_metadata(self):
        self.assertGreater(self.metadata["num_layers"], 0)
        self.assertGreater(self.metadata["num_heads"], 0)
        self.assertGreater(self.metadata["hidden_dim"], 0)
        self.assertGreater(self.metadata["total_params_b"], 0)

    def test_extract_embeddings(self):
        tokens = tokenize_text(self.tokenizer, "Hello AI")
        input_ids = [t["token_id"] for t in tokens]
        embed_data = extract_embeddings(self.model, input_ids)
        self.assertEqual(embed_data["embedding_matrix"].shape[0], len(input_ids))
        self.assertEqual(embed_data["embedding_matrix"].shape[1], self.metadata["hidden_dim"])
        self.assertEqual(len(embed_data["stats"]), len(input_ids))

    def test_forward_xray(self):
        tokens = tokenize_text(self.tokenizer, "Hello AI")
        input_ids = [t["token_id"] for t in tokens]
        outputs = forward_xray(self.model, input_ids)
        self.assertEqual(len(outputs["attentions"]), self.metadata["num_layers"])
        self.assertEqual(len(outputs["hidden_states"]), self.metadata["num_layers"] + 1)
        self.assertEqual(len(outputs["last_logits"]), self.metadata["vocab_size"])

    def test_compute_logits_and_probs(self):
        tokens = tokenize_text(self.tokenizer, "Hello AI")
        input_ids = [t["token_id"] for t in tokens]
        outputs = forward_xray(self.model, input_ids)
        probs = compute_logits_and_probs(outputs["last_logits"], self.tokenizer, top_k=5)
        self.assertEqual(len(probs), 5)
        self.assertEqual(probs[0]["rank"], 1)
        self.assertGreater(probs[0]["probability"], 0.0)

    def test_compute_logits_edge_cases(self):
        tokens = tokenize_text(self.tokenizer, "Test")
        input_ids = [t["token_id"] for t in tokens]
        outputs = forward_xray(self.model, input_ids)
        # Greedy (temp=0.0)
        probs_greedy = compute_logits_and_probs(outputs["last_logits"], self.tokenizer, top_k=1, temperature=0.0)
        self.assertEqual(len(probs_greedy), 1)
        # Nucleus top_p=0.5
        probs_top_p = compute_logits_and_probs(outputs["last_logits"], self.tokenizer, top_k=10, top_p=0.5)
        self.assertGreater(len(probs_top_p), 0)

    def test_generation_with_trace(self):
        prompt = "Hello"
        gen_text, traces = generate_with_xray_trace(
            self.model, self.tokenizer, prompt=prompt, max_new_tokens=3
        )
        self.assertIsInstance(gen_text, str)
        self.assertGreater(len(traces), 0)
        self.assertIn("chosen_token_id", traces[0])
        self.assertIn("top_candidates", traces[0])

    def test_greedy_generation(self):
        prompt = "The sky is"
        gen_text, traces = generate_with_xray_trace(
            self.model, self.tokenizer, prompt=prompt, max_new_tokens=3, temperature=0.0
        )
        self.assertIsInstance(gen_text, str)
        self.assertEqual(len(traces), 3)


class TestVisualizations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model_name = "Qwen/Qwen2.5-0.5B-Instruct"
        cls.model, cls.tokenizer, cls.device = load_model(cls.model_name, device="cpu")
        cls.metadata = get_model_metadata(cls.model)
        cls.prompt = "What is AI?"
        cls.tokens = tokenize_text(cls.tokenizer, cls.prompt)
        cls.input_ids = [t["token_id"] for t in cls.tokens]
        cls.embed_data = extract_embeddings(cls.model, cls.input_ids)
        cls.forward_out = forward_xray(cls.model, cls.input_ids)
        cls.probs = compute_logits_and_probs(cls.forward_out["last_logits"], cls.tokenizer, top_k=10)
        cls.gen_text, cls.traces = generate_with_xray_trace(
            cls.model, cls.tokenizer, prompt=cls.prompt, max_new_tokens=3
        )

    def test_pca_plot(self):
        fig = create_pca_embedding_plot(self.embed_data["embedding_matrix"], self.tokens)
        self.assertIsNotNone(fig)

    def test_embedding_heatmap(self):
        fig = create_embedding_heatmap_matrix(self.embed_data["embedding_matrix"], self.tokens)
        self.assertIsNotNone(fig)

    def test_attention_heatmap(self):
        att_layer = self.forward_out["attentions"][0]
        att_head = att_layer[0]
        fig = create_attention_heatmap(att_head, self.tokens, 0, 0)
        self.assertIsNotNone(fig)

    def test_hidden_states_pca_trajectory(self):
        fig = create_hidden_states_pca_trajectory(self.forward_out["hidden_states"], self.tokens, 0)
        self.assertIsNotNone(fig)

    def test_logits_bar_chart(self):
        fig = create_logits_bar_chart(self.probs, top_k=5)
        self.assertIsNotNone(fig)

    def test_step_generation_flow(self):
        fig, data = create_step_generation_flow(self.traces, 0)
        self.assertIsNotNone(fig)
        self.assertIn("chosen_token_id", data)

    def test_single_token_visualization(self):
        single_token = [self.tokens[0]]
        single_matrix = self.embed_data["embedding_matrix"][:1]
        fig_pca = create_pca_embedding_plot(single_matrix, single_token)
        self.assertIsNotNone(fig_pca)
        fig_heat = create_embedding_heatmap_matrix(single_matrix, single_token)
        self.assertIsNotNone(fig_heat)

    def test_empty_visualization_edge_cases(self):
        empty_matrix = np.zeros((0, self.metadata["hidden_dim"]))
        fig_pca = create_pca_embedding_plot(empty_matrix, [])
        self.assertIsNotNone(fig_pca)
        fig_heat = create_embedding_heatmap_matrix(empty_matrix, [])
        self.assertIsNotNone(fig_heat)
        fig_att = create_attention_heatmap(np.zeros((0, 0)), [], 0, 0)
        self.assertIsNotNone(fig_att)
        fig_traj = create_hidden_states_pca_trajectory([], [], 0)
        self.assertIsNotNone(fig_traj)


if __name__ == "__main__":
    unittest.main()
