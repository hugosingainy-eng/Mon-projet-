// Envoi des emails via SMTP (Gmail, OVH, Brevo, Mailjet, etc.).
import nodemailer from 'nodemailer';
import { config } from '../config.js';

export function smtpConfigured() {
  return Boolean(config.smtp.host && config.smtp.user && config.smtp.pass);
}

let transporter = null;
function getTransporter() {
  if (!transporter) {
    transporter = nodemailer.createTransport({
      host: config.smtp.host,
      port: config.smtp.port,
      secure: config.smtp.secure,
      auth: { user: config.smtp.user, pass: config.smtp.pass },
    });
  }
  return transporter;
}

export async function sendMail({ to, subject, html, text }) {
  if (!smtpConfigured()) throw new Error('SMTP non configuré (voir .env).');
  return getTransporter().sendMail({
    from: config.smtp.from,
    to,
    subject,
    html,
    text,
    headers: { 'List-Unsubscribe': `<mailto:${config.smtp.from}?subject=STOP>` },
  });
}
