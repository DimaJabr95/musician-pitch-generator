import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Home from "../app/page";

const LONG_BIO =
  "Dima is a Damascus-trained violinist based in Dubai, performing at weddings.";

const MOCK_RESULT = {
  angles: [
    "A Syrian violinist now performing in the UAE can compare audiences.",
    "Classical training meets Arabic maqam in a Dubai gallery set.",
  ],
  email_draft: {
    subject: "Dubai violinist blends classical and maqam",
    body: "Hi there, thought this might fit your desk.",
  },
};

function mockFetchOnce(response: Partial<Response>) {
  global.fetch = jest.fn().mockResolvedValue(response) as jest.Mock;
}

afterEach(() => {
  jest.restoreAllMocks();
});

test("renders the heading and a disabled submit button at first", () => {
  render(<Home />);

  expect(
    screen.getByRole("heading", { name: /find the story in your update/i }),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /find the angles/i })).toBeDisabled();
});

test("enables the button once the bio is at least 20 characters", async () => {
  const user = userEvent.setup();
  render(<Home />);

  await user.type(screen.getByRole("textbox"), LONG_BIO);

  expect(screen.getByRole("button", { name: /find the angles/i })).toBeEnabled();
});

test("shows the angles and draft email after a successful response", async () => {
  mockFetchOnce({ ok: true, json: async () => MOCK_RESULT });
  const user = userEvent.setup();
  render(<Home />);

  await user.type(screen.getByRole("textbox"), LONG_BIO);
  await user.click(screen.getByRole("button", { name: /find the angles/i }));

  expect(await screen.findByText(MOCK_RESULT.angles[0])).toBeInTheDocument();
  expect(screen.getByText(MOCK_RESULT.angles[1])).toBeInTheDocument();
  expect(screen.getByText(MOCK_RESULT.email_draft.subject)).toBeInTheDocument();
  expect(screen.getByText(MOCK_RESULT.email_draft.body)).toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledWith(
    expect.stringContaining("/generate-pitch"),
    expect.objectContaining({ method: "POST" }),
  );
});

test("shows the API's error message when the request fails", async () => {
  mockFetchOnce({
    ok: false,
    json: async () => ({ detail: "Too many requests right now." }),
  });
  const user = userEvent.setup();
  render(<Home />);

  await user.type(screen.getByRole("textbox"), LONG_BIO);
  await user.click(screen.getByRole("button", { name: /find the angles/i }));

  expect(await screen.findByText(/too many requests right now/i)).toBeInTheDocument();
});

test("shows an error message when the network call throws", async () => {
  global.fetch = jest.fn().mockRejectedValue(new Error("Network down")) as jest.Mock;
  const user = userEvent.setup();
  render(<Home />);

  await user.type(screen.getByRole("textbox"), LONG_BIO);
  await user.click(screen.getByRole("button", { name: /find the angles/i }));

  expect(await screen.findByText(/network down/i)).toBeInTheDocument();
});

test("copy button copies the draft and shows 'Copied'", async () => {
  mockFetchOnce({ ok: true, json: async () => MOCK_RESULT });
  const user = userEvent.setup(); // also provides a fake clipboard
  render(<Home />);

  await user.type(screen.getByRole("textbox"), LONG_BIO);
  await user.click(screen.getByRole("button", { name: /find the angles/i }));
  await user.click(await screen.findByRole("button", { name: /copy/i }));

  await waitFor(() =>
    expect(screen.getByRole("button", { name: /copied/i })).toBeInTheDocument(),
  );
  expect(await navigator.clipboard.readText()).toContain(
    "Subject: Dubai violinist blends classical and maqam",
  );
});

const MOCK_OUTLETS = [
  {
    name: "Emirates Arts Digest",
    type: "Arts and culture publication",
    region: "UAE",
    beat: "Galleries, exhibition openings, art fairs and cultural institutions in the UAE.",
    score: 0.642,
  },
  {
    name: "The Maqam Ledger",
    type: "Music criticism site",
    region: "Middle East",
    beat: "Arabic and world music, with a focus on artists blending traditional maqam.",
    score: 0.627,
  },
];

test("shows the best-fit outlets and marks the one the draft is written for", async () => {
  mockFetchOnce({
    ok: true,
    json: async () => ({ ...MOCK_RESULT, outlets: MOCK_OUTLETS }),
  });
  const user = userEvent.setup();
  render(<Home />);

  await user.type(screen.getByRole("textbox"), LONG_BIO);
  await user.click(screen.getByRole("button", { name: /find the angles/i }));

  expect(
    await screen.findByRole("heading", { name: /best-fit outlets/i }),
  ).toBeInTheDocument();
  expect(screen.getByText("Emirates Arts Digest")).toBeInTheDocument();
  expect(screen.getByText("The Maqam Ledger")).toBeInTheDocument();
  // only the first (top match) is marked as the one the draft targets
  expect(screen.getAllByText(/draft written for this outlet/i)).toHaveLength(1);
});

test("hides the outlets section when the API returns no outlets", async () => {
  mockFetchOnce({
    ok: true,
    json: async () => ({ ...MOCK_RESULT, outlets: [] }),
  });
  const user = userEvent.setup();
  render(<Home />);

  await user.type(screen.getByRole("textbox"), LONG_BIO);
  await user.click(screen.getByRole("button", { name: /find the angles/i }));

  expect(await screen.findByText(MOCK_RESULT.angles[0])).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: /best-fit outlets/i }),
  ).not.toBeInTheDocument();
});
