# Streamlit Cloud Deployment Guide

## Overview
This guide covers deploying the Price Tracker to Streamlit Cloud for public access and production use.

## Prerequisites
- GitHub account
- Streamlit Cloud account (free at https://share.streamlit.io/)
- All fixes and features tested locally

## Deployment Steps

### 1. GitHub Repository Setup

```bash
# Initialize git repository (if not already done)
git init

# Add all files
git add .

# Commit changes
git commit -m "Initial commit: Price Tracker with URL Manager fixes"

# Add remote repository
git remote add origin https://github.com/YOUR_USERNAME/price-tracker.git

# Push to GitHub
git push -u origin main
```

### 2. Streamlit Cloud Deployment

1. **Go to Streamlit Cloud**: https://share.streamlit.io/
2. **Sign in** with your GitHub account
3. **Click "New app"**
4. **Select your repository**: `YOUR_USERNAME/price-tracker`
5. **Set main file path**: `streamlit_app.py`
6. **Deploy**

### 3. Configuration for Cloud

The following files are configured for Streamlit Cloud:

- **`streamlit_app.py`**: Entry point for Streamlit Cloud
- **`.streamlit/config.toml`**: Streamlit configuration
- **`requirements.txt`**: Python dependencies
- **`.gitignore`**: Excludes local files from deployment

### 4. Database Initialization

After deployment, the database will be empty. You'll need to:

1. **Access the deployed app**
2. **Run the migration script** (if available in cloud environment)
3. **Or manually add initial data** through the URL Manager interface

### 5. Post-Deployment Verification

Test the following functionality:
- [ ] Dashboard loads correctly
- [ ] URL Manager displays retailers
- [ ] Can add new URLs successfully
- [ ] Price data displays (once populated)
- [ ] Export functionality works
- [ ] Health monitoring shows correct status

## Important Notes

### Database Considerations
- **Local Development**: Uses SQLite file (`data/price_tracker.db`)
- **Streamlit Cloud**: Database will reset on each deployment
- **Production**: Consider using persistent storage or cloud database

### Scraping Limitations
- **Streamlit Cloud**: Limited to dashboard functionality only
- **Scraping**: Requires separate hosting (Heroku, AWS, etc.) for automated scraping
- **Scheduling**: Not available on Streamlit Cloud free tier

### Security
- **No sensitive data**: Configuration files contain no secrets
- **Public access**: Dashboard will be publicly accessible
- **Rate limiting**: Consider implementing for production use

## Next Steps After Deployment

1. **Test URL Manager**: Verify all retailer combinations work
2. **Add initial URLs**: Use the interface to add product URLs
3. **Set up scraping**: Deploy scraping component separately
4. **Configure scheduling**: Set up automated price monitoring

## Troubleshooting

### Common Issues
- **Import errors**: Check `streamlit_app.py` path configuration
- **Missing dependencies**: Verify `requirements.txt` is complete
- **Database errors**: Database starts empty on first deployment

### Support
- **Streamlit Docs**: https://docs.streamlit.io/
- **Community Forum**: https://discuss.streamlit.io/
- **GitHub Issues**: Use repository issues for bug reports

## Production Considerations

For full production deployment:
1. **Database**: Use PostgreSQL or similar persistent database
2. **Scraping**: Deploy on cloud platform with scheduling
3. **Monitoring**: Set up alerts and health checks
4. **Backup**: Implement data backup strategy
5. **Security**: Add authentication if needed