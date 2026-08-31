export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Credentials', true);
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,PATCH,DELETE,POST,PUT');
    res.setHeader(
        'Access-Control-Allow-Headers',
        'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version'
    );

    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }

    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method Not Allowed' });
    }

    try {
        const { code, client_id, client_secret, redirect_uri } = req.body || {};

        if (!code || !client_id || !client_secret || !redirect_uri) {
            return res.status(400).json({ error: 'Missing required parameters: code, client_id, client_secret, redirect_uri' });
        }

        const params = new URLSearchParams({
            grant_type: 'authorization_code',
            code: code,
            client_id: client_id,
            client_secret: client_secret,
            redirect_uri: redirect_uri
        });

        const tokenRes = await fetch('https://www.linkedin.com/oauth/v2/accessToken', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: params.toString()
        });

        const tokenData = await tokenRes.json();

        if (!tokenRes.ok || tokenData.error) {
            return res.status(400).json({
                error: tokenData.error_description || tokenData.error || 'Failed to exchange token with LinkedIn'
            });
        }

        const accessToken = tokenData.access_token;
        const expiresIn = tokenData.expires_in || 5184000;
        const refreshToken = tokenData.refresh_token || accessToken;

        let memberUrn = '';
        try {
            const userRes = await fetch('https://api.linkedin.com/v2/userinfo', {
                headers: { 'Authorization': `Bearer ${accessToken}` }
            });
            if (userRes.ok) {
                const userData = await userRes.json();
                if (userData.sub) {
                    memberUrn = `urn:li:person:${userData.sub}`;
                }
            }
        } catch (e) {
            console.warn('Failed to fetch userinfo:', e);
        }

        const expiryDate = new Date(Date.now() + expiresIn * 1000).toISOString();

        return res.status(200).json({
            status: 'success',
            access_token: accessToken,
            refresh_token: refreshToken,
            member_urn: memberUrn,
            expires_in: expiresIn,
            token_expiry: expiryDate,
            secrets_summary: {
                LINKEDIN_ACCESS_TOKEN: accessToken,
                LINKEDIN_MEMBER_URN: memberUrn || 'urn:li:person:YOUR_MEMBER_URN',
                LINKEDIN_TOKEN_EXPIRY: expiryDate,
                LINKEDIN_REFRESH_TOKEN: refreshToken
            }
        });
    } catch (err) {
        return res.status(500).json({ error: err.message || 'Internal server error' });
    }
}
