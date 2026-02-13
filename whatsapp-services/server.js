const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');

const app = express();
app.use(express.json());

// WhatsApp Client
const client = new Client({
    authStrategy: new LocalAuth() // saves session locally
});

client.on('qr', (qr) => {
    console.log('Scan this QR code with WhatsApp:');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log('✅ WhatsApp Client is ready!');
});

client.initialize();

// API Endpoint to send message
app.post('/send-message', async (req, res) => {
    const { number, message } = req.body;

    try {
        await client.sendMessage(`${number}@c.us`, message);
        res.json({ status: 'Message sent successfully' });
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: 'Failed to send message' });
    }
});

// Start Server
app.listen(3000, () => {
    console.log('🚀 WhatsApp Service running on port 3000');
});
