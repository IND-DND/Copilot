'use strict';

const $ = (id) => document.getElementById(id);
const messages = $('messages');
const question = $('question');
let busy = false;
let controller = null;
let generation = 0;
let contextQuestion = null;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function safeLink(url, text) {
  const a = el('a', '', text.replace(/ ↗/g, ''));
  if (text.includes('↗')) { const arrow = el('span', 'link-arrow'); arrow.setAttribute('aria-hidden', 'true'); a.append(arrow); }
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'https:') a.href = parsed.href;
  } catch { /* Missing links remain plain text. */ }
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  return a;
}

function label(name, avatar) {
  const row = el('div', 'message-label');
  row.append(el('span', 'message-avatar', avatar), el('span', '', name));
  return row;
}

function scrollToLatest() {
  window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
}

function renderEvidence(source, language) {
  const hi = language === 'hi';
  const card = el('article', 'evidence-card');
  const title = el('div', 'evidence-title');
  title.append(safeLink(source.url, source.reference + ' ↗'), el('span', 'evidence-kind', source.kind === 'quran' ? 'Quran' : 'Hadith summary'));
  card.append(title);
  if (source.arabic) {
    const arabic = el('p', 'arabic-text', source.arabic);
    arabic.lang = 'ar';
    arabic.dir = 'rtl';
    card.append(arabic);
  }
  const text = el('p', 'translation-text', source.text);
  text.lang = language;
  card.append(text);
  if (source.footnotes) {
    const detail = el('details', 'footnotes');
    detail.append(el('summary', '', hi ? 'अनुवादक की टिप्पणियाँ' : 'Translator footnotes'), el('p', '', source.footnotes));
    card.append(detail);
  }
  const credit = el('div', 'evidence-credit');
  credit.append(el('div', '', `${source.publisher} · ${hi ? 'संस्करण' : 'Version'} ${source.version}`));
  credit.append(safeLink(source.license_url, source.license));
  if (source.note) credit.append(el('div', 'evidence-note', source.note));
  if (source.kind === 'quran') credit.append(safeLink('https://tanzil.net/docs/text_license', 'Arabic: Tanzil Project · CC BY 3.0 · text preserved verbatim'));
  card.append(credit);
  return card;
}

function renderResponse(data, container) {
  const hi = data.language === 'hi';
  container.append(label(hi ? 'नूर · उत्तर' : 'Noor · Response', '✦'));
  const p = el('p', 'assistant-text', data.response);
  p.lang = data.language;
  container.append(p);
  const meta = el('div', 'result-meta');
  const mode = data.mode === 'model' ? (hi ? 'AI व्याख्या · स्रोतों की जाँच करें' : 'AI explanation · review the sources') : (hi ? 'स्रोतों से प्राप्त उत्तर' : 'Source retrieval');
  meta.append(el('span', '', mode), el('span', '', data.source_mode === 'api' ? 'Approved source API' : data.source_mode === 'mixed' ? 'Local library + source API' : data.source_mode === 'none' ? (hi ? 'प्रमाणित स्रोत नहीं मिला' : 'No verified source found') : (hi ? 'स्थानीय ज्ञान संग्रह' : 'Local knowledge library')));
  container.append(meta);
  for (const notice of data.notices) container.append(el('div', 'notice', notice));
  for (const source of data.citations) container.append(renderEvidence(source, data.language));
  if (data.citations.some((s) => s.kind === 'quran')) {
    const notice = el('details', 'footnotes');
    notice.append(el('summary', '', hi ? 'अरबी पाठ: स्रोत और उपयोग की शर्तें' : 'Arabic text attribution & terms'));
    // The complete Tanzil notice is loaded from the preserved source manifest.
    const text = el('p', '', 'Tanzil Quran Text. Copyright (C) 2007–2021 Tanzil Project. CC BY 3.0; verbatim use only.');
    notice.append(text);
    container.append(notice);
    fetch('/api/sources').then((r) => r.json()).then((s) => { text.textContent = s.quran.arabic.notice; }).catch(() => {});
  }
}

async function submit(value) {
  const text = value.trim();
  if (!text || busy) return;
  if (text.length > 2000) { $('composer-error').textContent = 'Please keep your question under 2,000 characters.'; return; }
  busy = true;
  const currentGeneration = generation;
  controller = new AbortController();
  const requestController = controller;
  const timer = setTimeout(() => requestController.abort(), 90000);
  $('composer-error').textContent = '';
  $('welcome').hidden = true;
  $('send-button').disabled = true;
  const user = el('article', 'message');
  user.append(label('You · Query', '◌'), el('p', 'user-message', text));
  messages.append(user);
  const assistant = el('article', 'message');
  const loading = el('div', 'loading-text');
  for (let i = 0; i < 3; i++) loading.append(el('span', 'loading-dot'));
  loading.append(el('span', '', $('language').value === 'hi' ? 'स्रोतों में खोज जारी है…' : 'Finding relevant sources…'));
  assistant.append(loading);
  messages.append(assistant);
  question.value = '';
  question.style.height = 'auto';
  scrollToLatest();
  try {
    const response = await fetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: requestController.signal,
      body: JSON.stringify({ question: text, language: $('language').value, scope: $('scope').value, allow_external: true, context_question: contextQuestion }),
    });
    if (!response.ok) throw new Error(response.status === 422 ? 'Please check your question and try again.' : 'The assistant could not complete the request. Please try again.');
    const data = await response.json();
    if (currentGeneration !== generation) return;
    if (data.citations.length) contextQuestion = data.retrieval_query;
    assistant.replaceChildren();
    renderResponse(data, assistant);
    // Keep the beginning of a long response in view instead of jumping past it.
    assistant.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) {
    if (currentGeneration !== generation) return;
    assistant.replaceChildren();
    assistant.append(el('div', 'notice', error.name === 'AbortError' ? 'The request timed out. Please try again.' : error.message));
    question.value = text;
  } finally {
    clearTimeout(timer);
    if (currentGeneration === generation) {
      busy = false;
      controller = null;
      $('send-button').disabled = false;
      question.focus({ preventScroll: true });
    }
  }
}

function newChat() {
  generation++;
  contextQuestion = null;
  controller?.abort();
  controller = null;
  busy = false;
  messages.replaceChildren();
  $('welcome').hidden = false;
  $('send-button').disabled = false;
  $('composer-error').textContent = '';
  question.value = '';
  question.style.height = 'auto';
  window.scrollTo({ top: 0 });
  question.focus();
}

$('chat-form').addEventListener('submit', (event) => { event.preventDefault(); submit(question.value); });
question.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); submit(question.value); }
});
question.addEventListener('input', () => { question.style.height = 'auto'; question.style.height = Math.min(question.scrollHeight, 160) + 'px'; });
document.querySelectorAll('[data-question]').forEach((button) => button.addEventListener('click', () => { $('scope').value = 'all'; submit(button.dataset.question); }));
$('new-chat').addEventListener('click', newChat);
$('mobile-new-chat').addEventListener('click', newChat);
$('conversation-tab').addEventListener('click', () => question.focus());
document.addEventListener('keydown', (event) => {
  if (event.key.toLowerCase() === 'n' && !event.ctrlKey && !event.metaKey && !event.altKey && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName) && !document.querySelector('dialog[open]')) newChat();
});

async function showSources() {
  $('sources-dialog').showModal();
  try {
    const response = await fetch('/api/sources');
    if (!response.ok) throw new Error('Source information is unavailable.');
    const sources = await response.json();
    const content = $('sources-content');
    content.replaceChildren();
    const arabic = el('section', 'source-block');
    arabic.append(el('h3', '', 'Arabic Quran · Tanzil Project'), el('p', '', 'All 6,236 verses · Uthmani script · Hafs numbering. Text is retained verbatim, including Tanzil’s opening basmala conventions.'), safeLink(sources.quran.arabic.url, 'CC BY 3.0 · License & attribution ↗'), el('p', 'copyright-notice', sources.quran.arabic.notice));
    content.append(arabic);
    for (const edition of sources.quran.translations) {
      const block = el('section', 'source-block');
      block.append(el('h3', '', edition.title), el('p', '', `${edition.description} Version ${edition.version}. Published wording and translator footnotes are preserved.`), safeLink(sources.quran.translation_terms.url, 'QuranEnc.com · Republication terms ↗'));
      content.append(block);
    }
    const hadith = el('section', 'source-block');
    hadith.append(el('h3', '', 'Selected Hadith · original summaries'), el('p', '', 'Five references from Sahih al-Bukhari and Sahih Muslim. These are original explanatory summaries, not copied translations. These collections reflect Sunni tradition. Numbering can vary by edition.'));
    for (const entry of sources.hadith) { const p = el('p'); p.append(safeLink(entry.url, entry.reference + ' ↗')); hadith.append(p); }
    content.append(hadith);
    const provenance = el('section', 'source-block');
    provenance.append(el('h3', '', 'Dataset provenance'), el('p', '', `Mirror: ${sources.quran.dataset}. Pinned revision ${sources.quran.commit.slice(0, 12)}. The dataset uses ${sources.quran.dataset_license}; each source retains its own terms. Optional external lookups fetch this same licensed, checksum-verified snapshot, not arbitrary website search.`), safeLink(sources.quran.source_url, 'Dataset repository ↗'));
    content.append(provenance);
  } catch (error) { $('sources-content').textContent = error.message; }
}

$('sources-button').addEventListener('click', showSources);
$('mobile-sources').addEventListener('click', showSources);
$('about-button').addEventListener('click', () => $('about-dialog').showModal());
document.querySelectorAll('.close-dialog').forEach((button) => button.addEventListener('click', () => button.closest('dialog').close()));
document.querySelectorAll('dialog').forEach((dialog) => dialog.addEventListener('click', (event) => { if (event.target === dialog) { const box = dialog.getBoundingClientRect(); if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close(); } }));

fetch('/api/health').then((r) => { if (!r.ok) throw new Error(); return r.json(); }).then((health) => { $('connection-status').textContent = health.model_enabled ? 'Library + local model configured' : 'Knowledge library ready'; }).catch(() => { $('connection-status').textContent = 'Library unavailable'; });
